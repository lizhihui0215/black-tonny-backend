from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.capture.admissions import build_inventory_capture_admission_bundle
from app.services.research.menu_coverage import (
    infer_domain_from_menu_metadata,
    load_latest_menu_coverage_audit,
)


LEDGER_SPECS = (
    ("sales", "销售", Path("docs/erp/sales-ledger.md")),
    ("inventory", "库存", Path("docs/erp/inventory-ledger.md")),
    ("member", "会员", Path("docs/erp/member-ledger.md")),
    ("stored_value", "储值", Path("docs/erp/stored-value-ledger.md")),
    ("payment_and_docs", "流水单据", Path("docs/erp/payment-and-doc-ledger.md")),
)

DOMAIN_ORDER = {
    "sales": 0,
    "inventory": 1,
    "member": 2,
    "stored_value": 3,
    "payment_and_docs": 4,
}

STAGE_ORDER = {
    "已发现": 0,
    "已基线": 1,
    "已单变量": 2,
    "已HTTP回证": 3,
    "已准入主链": 4,
}

ROLE_ORDER = {
    "主源候选": 0,
    "对账源": 1,
    "研究留痕": 2,
    "结果快照": 3,
    "未采纳": 4,
    "待识别": 5,
}

RELIABILITY_ORDER = {
    "能跑但不能信": 0,
    "中等可信": 1,
    "高可信": 2,
}

PAGE_RESEARCH_ALIASES = {
    "会员消费排行": ("会员消费排行榜",),
    "库存总和分析-按年份季节": ("库存综合分析-按年份季节",),
    "库存总和分析-按中分类": ("库存综合分析-按中分类",),
    "库存总和分析-按波段": ("库存综合分析-按波段分析",),
}
SETTINGS_PAGE_TITLES = {
    "VIP卡折扣管理",
    "参数设置",
    "导购员设置",
    "小票设置",
    "店铺定位",
}


@dataclass(frozen=True)
class BoardSourceFiles:
    report_matrix: Path | None
    page_research_files: tuple[Path, ...]
    sales_evidence: Path | None
    inventory_evidence: Path | None
    store_stocktaking_evidence: Path | None
    store_stocktaking_ui_probe: Path | None
    return_detail_evidence: Path | None
    return_detail_ui_probe: Path | None
    receipt_confirmation_evidence: Path | None
    receipt_confirmation_ui_probe: Path | None
    member_evidence: Path | None
    member_maintenance_evidence: Path | None
    member_analysis_snapshot_evidence: Path | None
    member_sales_rank_snapshot_evidence: Path | None
    product_evidence: Path | None
    product_sales_snapshot_evidence: Path | None
    daily_payment_snapshot_evidence: Path | None
    stored_value_card_summary_snapshot_evidence: Path | None
    stored_value_by_store_snapshot_evidence: Path | None
    customer_evidence: Path | None
    stored_value_evidence: Path | None
    inventory_outin_research: Path | None
    menu_coverage_audit: Path | None
    capture_runtime_files: tuple[Path, ...]


def _repo_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _latest_json(analysis_root: Path, pattern: str) -> Path | None:
    candidates = sorted(analysis_root.glob(pattern))
    return candidates[-1] if candidates else None


def _all_json(analysis_root: Path, pattern: str) -> tuple[Path, ...]:
    return tuple(sorted(analysis_root.glob(pattern)))


def _load_json(path: Path | None) -> Any:
    if path is None:
        return None
    return json.loads(path.read_text("utf-8"))


def _parse_markdown_table(text: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    table_lines: list[str] = []
    in_table = False
    for line in lines:
        if line.startswith("|"):
            table_lines.append(line)
            in_table = True
            continue
        if in_table:
            break
    if len(table_lines) < 2:
        return []

    headers = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in table_lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells, strict=True)))
    return rows


def load_ledger_routes(repo_root: Path) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for domain_key, domain_label, relative_path in LEDGER_SPECS:
        path = repo_root / relative_path
        rows = _parse_markdown_table(path.read_text("utf-8"))
        for row in rows:
            title = row.get("页面/报表", "").strip()
            endpoint = row.get("endpoint", "").strip().strip("`")
            dedupe_key = (title, endpoint)
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            routes.append(
                {
                    "domain": domain_key,
                    "domain_label": domain_label,
                    "title": title,
                    "endpoint": endpoint,
                    "method": row.get("method", "").strip().strip("`"),
                    "auth_mode": row.get("认证方式", "").strip().strip("`"),
                    "filter_fields_summary": row.get("主要过滤字段", "").strip().strip("`"),
                    "current_judgment": row.get("当前判断", "").strip(),
                    "risk_labels": [item.strip() for item in row.get("风险标签", "").split("、") if item.strip()],
                    "capture_strategy": row.get("抓取策略", "").strip(),
                    "ledger_path": str(relative_path),
                }
            )
    return routes


def _page_record_score(page: dict[str, Any]) -> tuple[int, int]:
    probe_count = len(page.get("single_variable_probe_results") or [])
    endpoint_count = len(page.get("endpoint_summaries") or [])
    status_score = 1 if page.get("status") == "ok" else 0
    return (status_score, probe_count * 10 + endpoint_count)


def load_best_page_research(repo_root: Path, analysis_root: Path) -> tuple[dict[str, dict[str, Any]], tuple[Path, ...]]:
    page_files = _all_json(analysis_root, "yeusoft-page-research-*.json")
    best: dict[str, dict[str, Any]] = {}
    best_score: dict[str, tuple[int, int, str]] = {}
    for path in page_files:
        payload = _load_json(path) or {}
        for page in payload.get("pages", []):
            title = page.get("title")
            if not title:
                continue
            score = _page_record_score(page)
            score_key = (score[0], score[1], _repo_path(path, repo_root))
            if title not in best or score_key > best_score[title]:
                record = dict(page)
                record["_source_path"] = _repo_path(path, repo_root)
                best[title] = record
                best_score[title] = score_key
    return best, page_files


def resolve_page_research_record(title: str, page_records: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if title in page_records:
        return page_records[title]
    for alias in PAGE_RESEARCH_ALIASES.get(title, ()):
        if alias in page_records:
            return page_records[alias]
    return None


def _coverage_status_rank(status: str) -> int:
    order = {
        "covered": 0,
        "visible_but_failed": 1,
        "visible_but_untracked": 2,
        "container_only": 3,
        "not_visible_in_current_menu": 4,
    }
    return order.get(status, 99)


def _coverage_confidence_rank(confidence: str) -> int:
    order = {"high": 0, "medium": 1, "low": 2}
    return order.get(confidence, 99)


def _build_menu_coverage_index(menu_coverage_payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not menu_coverage_payload:
        return {}
    indexed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for page in menu_coverage_payload.get("pages", []):
        for key in filter(
            None,
            [
                str(page.get("title") or "").strip(),
                str(page.get("page_title") or "").strip(),
                *(str(item).strip() for item in page.get("matched_registry_titles") or []),
            ],
        ):
            indexed[key].append(page)
    resolved: dict[str, dict[str, Any]] = {}
    for key, pages in indexed.items():
        resolved[key] = sorted(
            pages,
            key=lambda item: (
                _coverage_status_rank(str(item.get("coverage_status") or "")),
                _coverage_confidence_rank(str(item.get("coverage_confidence") or "")),
                str(item.get("title") or ""),
            ),
        )[0]
    return resolved


def resolve_menu_coverage_page(title: str, menu_coverage_index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if title in menu_coverage_index:
        return menu_coverage_index[title]
    for alias in PAGE_RESEARCH_ALIASES.get(title, ()):
        if alias in menu_coverage_index:
            return menu_coverage_index[alias]
    return None


def load_report_matrix(analysis_root: Path) -> tuple[Path | None, dict[str, Any]]:
    path = _latest_json(analysis_root, "report-matrix-*.json")
    payload = _load_json(path) or []
    return path, {item.get("title"): item for item in payload if item.get("title")}


def load_sales_evidence(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "sales-evidence-chain-*.json")
    payload = _load_json(path)
    return path, payload


def load_inventory_evidence(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "inventory-evidence-chain-*.json")
    payload = _load_json(path)
    return path, payload


def load_store_stocktaking_evidence(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "store-stocktaking-evidence-chain-*.json")
    payload = _load_json(path)
    return path, payload


def load_store_stocktaking_ui_probe(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "store-stocktaking-ui-probe-*.json")
    payload = _load_json(path)
    return path, payload


def load_return_detail_evidence(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "return-detail-evidence-chain-*.json")
    payload = _load_json(path)
    return path, payload


def load_return_detail_ui_probe(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "return-detail-ui-probe-*.json")
    payload = _load_json(path)
    return path, payload


def load_receipt_confirmation_evidence(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "receipt-confirmation-evidence-chain-*.json")
    payload = _load_json(path)
    return path, payload


def load_receipt_confirmation_ui_probe(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "receipt-confirmation-ui-probe-*.json")
    payload = _load_json(path)
    return path, payload


def load_member_evidence(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "member-evidence-chain-*.json")
    payload = _load_json(path)
    return path, payload


def load_member_maintenance_evidence(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "member-maintenance-evidence-chain-*.json")
    payload = _load_json(path)
    return path, payload


def load_member_analysis_snapshot_evidence(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "member-analysis-snapshot-evidence-chain-*.json")
    payload = _load_json(path)
    return path, payload


def load_member_sales_rank_snapshot_evidence(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "member-sales-rank-snapshot-evidence-chain-*.json")
    payload = _load_json(path)
    return path, payload


def load_product_evidence(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "product-evidence-chain-*.json")
    payload = _load_json(path)
    return path, payload


def load_product_sales_snapshot_evidence(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "product-sales-snapshot-evidence-chain-*.json")
    payload = _load_json(path)
    return path, payload


def load_daily_payment_snapshot_evidence(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "daily-payment-snapshot-evidence-chain-*.json")
    payload = _load_json(path)
    return path, payload


def load_stored_value_card_summary_snapshot_evidence(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "stored-value-card-summary-snapshot-evidence-chain-*.json")
    payload = _load_json(path)
    return path, payload


def load_stored_value_by_store_snapshot_evidence(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "stored-value-by-store-snapshot-evidence-chain-*.json")
    payload = _load_json(path)
    return path, payload


def load_customer_evidence(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "customer-evidence-chain-*.json")
    payload = _load_json(path)
    return path, payload


def load_stored_value_evidence(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "stored-value-evidence-chain-*.json")
    payload = _load_json(path)
    return path, payload


def load_inventory_outin_research(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "inventory-outin-capture-research-*.json")
    payload = _load_json(path)
    return path, payload


def load_capture_runtime_state(
    repo_root: Path,
    analysis_root: Path,
) -> tuple[dict[str, dict[str, Any]], tuple[Path, ...]]:
    runtime_index: dict[str, dict[str, Any]] = {}
    files = sorted(
        path
        for pattern in (
            "sales-capture-admission-*.json",
            "inventory-stock-capture-admission-*.json",
            "inventory-outin-capture-research-*.json",
            "inventory-outin-capture-admission-*.json",
            "member-capture-admission-*.json",
            "member-capture-research-*.json",
            "member-analysis-snapshot-capture-admission-*.json",
            "member-maintenance-capture-admission-*.json",
            "member-maintenance-capture-research-*.json",
            "member-sales-rank-snapshot-capture-admission-*.json",
            "product-capture-admission-*.json",
            "product-capture-research-*.json",
            "product-sales-snapshot-capture-admission-*.json",
            "daily-payment-snapshot-capture-admission-*.json",
            "stored-value-card-summary-snapshot-capture-admission-*.json",
            "stored-value-by-store-snapshot-capture-admission-*.json",
            "customer-capture-admission-*.json",
            "customer-capture-research-*.json",
            "return-detail-capture-research-*.json",
            "stored-value-capture-admission-*.json",
            "stored-value-capture-research-*.json",
            "receipt-confirmation-capture-admission-*.json",
            "receipt-confirmation-capture-research-*.json",
            "store-stocktaking-capture-admission-*.json",
            "store-stocktaking-capture-research-*.json",
            "store-stocktaking-diff-capture-research-*.json",
        )
        for path in analysis_root.glob(pattern)
    )

    def _register(route: str, *, mode: str, payload: dict[str, Any], path: Path) -> None:
        capture_batch_id = payload.get("capture_batch_id")
        if not capture_batch_id:
            return
        runtime_index[route] = {
            "capture_written_once": True,
            "latest_capture_batch_id": str(capture_batch_id),
            "latest_capture_mode": mode,
            "latest_capture_artifact": _repo_path(path, repo_root),
            "latest_capture_source_endpoint": payload.get("source_endpoint")
            or payload.get("document_source_endpoint")
            or payload.get("detail_source_endpoint"),
        }

    for path in files:
        payload = _load_json(path)
        if not isinstance(payload, dict):
            continue
        filename = path.name
        if filename.startswith("sales-capture-admission-"):
            _register("SelSaleReport", mode="admission", payload=payload, path=path)
            _register("GetDIYReportData(E004001008_2)", mode="admission", payload=payload, path=path)
            _register("sales_reverse_document_lines", mode="research", payload=payload, path=path)
            continue
        if filename.startswith("inventory-stock-capture-admission-"):
            _register("库存明细统计 / SelDeptStockWaitList", mode="admission", payload=payload, path=path)
            continue
        if filename.startswith("inventory-outin-capture-admission-"):
            _register("出入库单据 / SelOutInStockReport", mode="admission", payload=payload, path=path)
            continue
        if filename.startswith("inventory-outin-capture-research-") and "出入库单据 / SelOutInStockReport" not in runtime_index:
            _register("出入库单据 / SelOutInStockReport", mode="research", payload=payload, path=path)
            continue
        if filename.startswith("member-capture-admission-"):
            _register("会员中心 / SelVipInfoList", mode="admission", payload=payload, path=path)
            continue
        if filename.startswith("member-capture-research-"):
            if "会员中心 / SelVipInfoList" not in runtime_index:
                _register("会员中心 / SelVipInfoList", mode="research", payload=payload, path=path)
            continue
        if filename.startswith("member-analysis-snapshot-capture-admission-"):
            _register("会员总和分析 / SelVipAnalysisReport", mode="admission", payload=payload, path=path)
            continue
        if filename.startswith("member-maintenance-capture-admission-"):
            _register("会员维护 / SelVipReturnVisitList", mode="admission", payload=payload, path=path)
            continue
        if filename.startswith("member-maintenance-capture-research-"):
            if "会员维护 / SelVipReturnVisitList" not in runtime_index:
                _register("会员维护 / SelVipReturnVisitList", mode="research", payload=payload, path=path)
            continue
        if filename.startswith("member-sales-rank-snapshot-capture-admission-"):
            _register("会员消费排行 / SelVipSaleRank", mode="admission", payload=payload, path=path)
            continue
        if filename.startswith("product-capture-admission-"):
            _register("商品资料 / SelWareList", mode="admission", payload=payload, path=path)
            continue
        if filename.startswith("product-capture-research-"):
            if "商品资料 / SelWareList" not in runtime_index:
                _register("商品资料 / SelWareList", mode="research", payload=payload, path=path)
            continue
        if filename.startswith("product-sales-snapshot-capture-admission-"):
            _register("商品销售情况 / SelSaleReportData", mode="admission", payload=payload, path=path)
            continue
        if filename.startswith("daily-payment-snapshot-capture-admission-"):
            _register("每日流水单 / SelectRetailDocPaymentSlip", mode="admission", payload=payload, path=path)
            continue
        if filename.startswith("stored-value-card-summary-snapshot-capture-admission-"):
            _register("储值卡汇总 / GetDIYReportData", mode="admission", payload=payload, path=path)
            continue
        if filename.startswith("stored-value-by-store-snapshot-capture-admission-"):
            _register("储值按店汇总 / GetDIYReportData", mode="admission", payload=payload, path=path)
            continue
        if filename.startswith("customer-capture-admission-"):
            _register("客户资料 / SelDeptList", mode="admission", payload=payload, path=path)
            continue
        if filename.startswith("customer-capture-research-"):
            if "客户资料 / SelDeptList" not in runtime_index:
                _register("客户资料 / SelDeptList", mode="research", payload=payload, path=path)
            continue
        if filename.startswith("return-detail-capture-research-"):
            if "退货明细 / SelReturnStockList" not in runtime_index:
                _register("退货明细 / SelReturnStockList", mode="research", payload=payload, path=path)
            continue
        if filename.startswith("stored-value-capture-admission-"):
            _register("储值卡明细 / GetDIYReportData", mode="admission", payload=payload, path=path)
            continue
        if filename.startswith("stored-value-capture-research-"):
            if "储值卡明细 / GetDIYReportData" not in runtime_index:
                _register("储值卡明细 / GetDIYReportData", mode="research", payload=payload, path=path)
            continue
        if filename.startswith("receipt-confirmation-capture-admission-"):
            _register("收货确认 / SelDocConfirmList", mode="admission", payload=payload, path=path)
            continue
        if filename.startswith("receipt-confirmation-capture-research-"):
            if "收货确认 / SelDocConfirmList" not in runtime_index:
                _register("收货确认 / SelDocConfirmList", mode="research", payload=payload, path=path)
            continue
        if filename.startswith("store-stocktaking-capture-admission-"):
            _register("门店盘点单 / SelDocManageList", mode="admission", payload=payload, path=path)
            continue
        if filename.startswith("store-stocktaking-capture-research-"):
            if "门店盘点单 / SelDocManageList" not in runtime_index:
                _register("门店盘点单 / SelDocManageList", mode="research", payload=payload, path=path)
            continue
        if filename.startswith("store-stocktaking-diff-capture-research-"):
            _register("门店盘点单 / store_stocktaking_diff_records", mode="research", payload=payload, path=path)

    return runtime_index, tuple(files)


def _short_endpoint(endpoint: str) -> str:
    endpoint = endpoint.strip().strip("`")
    if "/" not in endpoint:
        return endpoint
    return endpoint.rsplit("/", 1)[-1]


def _default_role(route: dict[str, Any]) -> str:
    title = route["title"]
    strategy = route["capture_strategy"]
    current = route["current_judgment"]
    if title == "零售明细统计":
        return "对账源"
    if strategy == "暂不采纳":
        return "未采纳"
    if strategy == "结果快照" or "结果接口" in current or "结果视图" in current or "快照" in current:
        return "结果快照"
    if "对账" in current:
        return "对账源"
    return "主源候选"


def _default_stage(route: dict[str, Any], page_record: dict[str, Any] | None) -> str:
    if page_record is None:
        return "已发现"
    if page_record.get("single_variable_probe_results"):
        return "已单变量"
    return "已基线"


def _stage_blocks(stage: str, role: str) -> list[str]:
    if stage == "已发现":
        return ["尚未完成页面基线研究"]
    if stage == "已基线":
        if role == "结果快照":
            return ["尚未完成分页/枚举确认"]
        return ["尚未完成单变量探测", "尚未完成 HTTP 回证"]
    if stage == "已单变量":
        if role == "结果快照":
            return ["尚未确认是否只保留结果快照定位"]
        return ["尚未完成 HTTP 回证"]
    return []


def _default_next_action(stage: str, role: str, title: str) -> str:
    if stage == "已发现":
        return f"先补 {title} 的页面基线研究"
    if stage == "已基线":
        if role == "结果快照":
            return f"补 {title} 的分页/枚举确认，保持结果快照定位"
        return f"补 {title} 的单变量探测与 HTTP 回证"
    if stage == "已单变量":
        if role == "结果快照":
            return f"确认 {title} 是否继续只做结果快照"
        return f"补 {title} 的纯 HTTP 回证并收口 blocker"
    if stage == "已HTTP回证":
        return f"继续收口 {title} 的剩余 blocker，再评估主链准入"
    return "保持主链回归监控"


def _default_trust(stage: str, role: str, has_blockers: bool) -> str:
    if stage == "已准入主链":
        return "高"
    if stage == "已HTTP回证":
        return "中" if has_blockers else "高"
    if stage == "已单变量":
        return "中"
    if role == "结果快照" and stage == "已基线":
        return "低"
    return "低"


def _coverage_scope(route: dict[str, Any], page_record: dict[str, Any] | None) -> list[str]:
    tags = ["当前账号范围"]
    if page_record:
        grain_route = page_record.get("grain_route")
        if grain_route == "multi_grain_route":
            tags.append("多粒度")
        elif grain_route == "enum_or_scope_route":
            tags.append("存在范围或枚举切换")
        elif grain_route == "single_route":
            tags.append("单路线")
        hints = page_record.get("payload_hints") or {}
        if hints.get("pagination_fields") or "需要翻页" in route["risk_labels"]:
            tags.append("存在分页")
        if hints.get("enum_fields") or "需要扫枚举" in route["risk_labels"]:
            tags.append("存在枚举")
    else:
        if "需要翻页" in route["risk_labels"]:
            tags.append("存在分页")
        if "需要扫枚举" in route["risk_labels"]:
            tags.append("存在枚举")
    if route["capture_strategy"] == "结果快照":
        tags.append("结果快照定位")
    return tags


def _coverage_metadata(menu_coverage_page: dict[str, Any] | None) -> dict[str, Any]:
    if not menu_coverage_page:
        return {
            "menu_path": [],
            "menu_root_name": "",
            "page_title": "",
            "coverage_status": "not_visible_in_current_menu",
            "coverage_confidence": "low",
        }
    return {
        "menu_path": list(menu_coverage_page.get("menu_path") or []),
        "menu_root_name": str(menu_coverage_page.get("root_name") or ""),
        "page_title": str(menu_coverage_page.get("page_title") or menu_coverage_page.get("title") or ""),
        "coverage_status": str(menu_coverage_page.get("coverage_status") or "visible_but_failed"),
        "coverage_confidence": str(menu_coverage_page.get("coverage_confidence") or "low"),
    }


def _build_generic_entry(
    route: dict[str, Any],
    page_record: dict[str, Any] | None,
    menu_coverage_page: dict[str, Any] | None,
) -> dict[str, Any]:
    role = _default_role(route)
    stage = _default_stage(route, page_record)
    blockers = _stage_blocks(stage, role)
    next_action = _default_next_action(stage, role, route["title"])
    trust_level = _default_trust(stage, role, bool(blockers))
    coverage = _coverage_metadata(menu_coverage_page)
    research_map_complete = stage != "已发现" and coverage["coverage_status"] != "not_visible_in_current_menu"
    return {
        "domain": route["domain"],
        "domain_label": route["domain_label"],
        "route": f"{route['title']} / {_short_endpoint(route['endpoint'])}",
        "title": route["title"],
        "endpoint": route["endpoint"],
        "role": role,
        "source_kind": role,
        "stage": stage,
        "trust_level": trust_level,
        "reliability_status": "能跑但不能信" if trust_level == "低" else ("中等可信" if trust_level == "中" else "高可信"),
        "coverage_scope": _coverage_scope(route, page_record),
        "research_map_complete": research_map_complete,
        "ingestion_blocked_by_global_gate": True,
        "mainline_ready": False,
        "blocking_issues": blockers,
        "next_action": next_action,
        "current_judgment": route["current_judgment"],
        "capture_strategy": route["capture_strategy"],
        "risk_labels": route["risk_labels"],
        "ledger_path": route["ledger_path"],
        "analysis_sources": [page_record["_source_path"]] if page_record else [],
        **coverage,
    }


def _build_sales_evidence_entries(
    *,
    sales_evidence: dict[str, Any],
    routes_by_title: dict[str, dict[str, Any]],
    page_records: dict[str, dict[str, Any]],
    menu_coverage_index: dict[str, dict[str, Any]],
    repo_root: Path,
    sales_evidence_path: Path,
) -> list[dict[str, Any]]:
    sales_route = routes_by_title["销售清单"]
    retail_route = routes_by_title["零售明细统计"]
    sales_page = resolve_page_research_record("销售清单", page_records)
    retail_page = resolve_page_research_record("零售明细统计", page_records)
    sales_coverage = _coverage_metadata(resolve_menu_coverage_page("销售清单", menu_coverage_index))
    retail_coverage = _coverage_metadata(resolve_menu_coverage_page("零售明细统计", menu_coverage_index))
    issue_flags = list(sales_evidence.get("issue_flags") or [])
    join_analysis = sales_evidence.get("join_key_analysis") or {}
    detail_only_profile = sales_evidence.get("detail_only_sale_no_profile") or {}
    capture_admission = sales_evidence.get("capture_admission") or {}
    candidate_keys = {
        item.get("key"): item for item in join_analysis.get("candidate_keys", []) if item.get("key")
    }
    detail_only_sale_no_count = int(detail_only_profile.get("detail_only_sale_no_count") or 0)
    reverse_split_ready = bool(capture_admission.get("reverse_split_ready"))
    capture_admission_ready = bool(capture_admission.get("capture_admission_ready"))
    reverse_route_blocking_issues = list(capture_admission.get("reverse_route_blocking_issues") or [])
    head_document_uniqueness = capture_admission.get("head_document_uniqueness") or {}
    head_document_uniqueness_ok = bool(head_document_uniqueness.get("head_document_uniqueness_ok"))

    shared_analysis_sources = [_repo_path(sales_evidence_path, repo_root)]
    if sales_page:
        shared_analysis_sources.append(sales_page["_source_path"])
    if retail_page:
        shared_analysis_sources.append(retail_page["_source_path"])
    shared_analysis_sources = list(dict.fromkeys(shared_analysis_sources))

    document_entry = {
        "domain": "sales",
        "domain_label": "销售",
        "route": "SelSaleReport",
        "title": "销售清单",
        "endpoint": "YisEposReport/SelSaleReport",
        "role": "主源候选",
        "source_kind": "主源候选",
        "stage": "已HTTP回证",
        "trust_level": "中",
        "reliability_status": "中等可信",
        "coverage_scope": ["当前账号范围", "多粒度", "单据头路线", "已完成 HTTP 回证"],
        "research_map_complete": True,
        "ingestion_blocked_by_global_gate": True,
        "mainline_ready": False,
        "blocking_issues": [] if head_document_uniqueness_ok else ["订单头唯一性仍待验证"],
        "next_action": (
            "已具备首批 capture 准入条件，保持 serving 冻结并先观测批次回归指标"
            if head_document_uniqueness_ok and capture_admission_ready
            else "验证订单头唯一性并准备首批 capture 准入"
        ),
        "current_judgment": "订单头候选源",
        "capture_strategy": "单请求",
        "risk_labels": sales_route["risk_labels"],
        "ledger_path": sales_route["ledger_path"],
        "analysis_sources": shared_analysis_sources,
        "candidate_join_keys": [
            key for key in ("sale_no", "sale_date", "vip_card_no") if key in candidate_keys
        ],
        "reverse_split_ready": reverse_split_ready,
        "capture_admission_ready": head_document_uniqueness_ok and capture_admission_ready,
        "reverse_route_blocking_issues": [],
        **sales_coverage,
    }
    detail_entry = {
        "domain": "sales",
        "domain_label": "销售",
        "route": "GetDIYReportData(E004001008_2)",
        "title": "销售清单",
        "endpoint": "FXDIYReport/GetDIYReportData",
        "role": "主源候选",
        "source_kind": "主源候选",
        "stage": "已HTTP回证",
        "trust_level": "中",
        "reliability_status": "中等可信",
        "coverage_scope": ["当前账号范围", "多粒度", "明细行路线", "Tiem 已确认同数据集"],
        "research_map_complete": True,
        "ingestion_blocked_by_global_gate": True,
        "mainline_ready": False,
        "blocking_issues": reverse_route_blocking_issues,
        "next_action": (
            "已可按 sale_no 分流正常明细与逆向明细，准备首批 capture 准入"
            if reverse_split_ready and capture_admission_ready
            else "按 sale_no 分流正常/逆向路线，并验证逆向分流稳定性"
        ),
        "current_judgment": "明细行候选源",
        "capture_strategy": "单请求",
        "risk_labels": sales_route["risk_labels"],
        "ledger_path": sales_route["ledger_path"],
        "analysis_sources": shared_analysis_sources,
        "candidate_join_keys": [
            key for key in ("sale_no", "sale_date", "vip_card_no") if key in candidate_keys
        ],
        "reverse_split_ready": reverse_split_ready,
        "capture_admission_ready": reverse_split_ready and capture_admission_ready,
        "reverse_route_blocking_issues": reverse_route_blocking_issues,
        **sales_coverage,
    }
    reverse_entry = {
        "domain": "sales",
        "domain_label": "销售",
        "route": "sales_reverse_document_lines",
        "title": "销售清单",
        "endpoint": "sales_reverse_document_lines",
        "role": "研究留痕",
        "source_kind": "研究留痕",
        "stage": "已HTTP回证",
        "trust_level": "中",
        "reliability_status": "中等可信",
        "coverage_scope": ["当前账号范围", "逆向/退换货疑似单据", "仅保留 capture 研究留痕"],
        "research_map_complete": True,
        "ingestion_blocked_by_global_gate": True,
        "mainline_ready": False,
        "blocking_issues": reverse_route_blocking_issues,
        "next_action": "继续保持 capture 研究留痕，不进入 serving 或 dashboard 主链",
        "current_judgment": (
            f"已识别 {detail_only_sale_no_count} 个仅明细出现的 sale_no，需作为逆向路线单独保留"
        ),
        "capture_strategy": "单请求",
        "risk_labels": ["逆向路线", "退货/换货待分流"],
        "ledger_path": sales_route["ledger_path"],
        "analysis_sources": shared_analysis_sources,
        "candidate_join_keys": ["sale_no"],
        "reverse_split_ready": reverse_split_ready,
        "capture_admission_ready": False,
        "reverse_route_blocking_issues": reverse_route_blocking_issues,
        **sales_coverage,
    }
    retail_entry = {
        "domain": "sales",
        "domain_label": "销售",
        "route": "SelDeptSaleList",
        "title": "零售明细统计",
        "endpoint": retail_route["endpoint"],
        "role": "对账源",
        "source_kind": "对账源",
        "stage": "已HTTP回证",
        "trust_level": "中",
        "reliability_status": "中等可信",
        "coverage_scope": ["当前账号范围", "存在分页", "研究/对账定位"],
        "research_map_complete": True,
        "ingestion_blocked_by_global_gate": True,
        "mainline_ready": False,
        "blocking_issues": [],
        "next_action": "保持研究/对账源定位，补充极端单日窗口的 edge case 说明即可",
        "current_judgment": "研究/对账源（宽表聚合，不直接承担订单数对账）",
        "capture_strategy": "自动翻页",
        "risk_labels": retail_route["risk_labels"],
        "ledger_path": retail_route["ledger_path"],
        "analysis_sources": shared_analysis_sources,
        "issue_flags": issue_flags,
        "reverse_split_ready": False,
        "capture_admission_ready": False,
        "reverse_route_blocking_issues": [],
        **retail_coverage,
    }
    return [document_entry, detail_entry, reverse_entry, retail_entry]


def _build_inventory_evidence_entries(
    *,
    inventory_evidence: dict[str, Any],
    inventory_admission: dict[str, Any],
    inventory_outin_research_path: Path | None,
    routes_by_title: dict[str, dict[str, Any]],
    page_records: dict[str, dict[str, Any]],
    menu_coverage_index: dict[str, dict[str, Any]],
    repo_root: Path,
    inventory_evidence_path: Path,
) -> list[dict[str, Any]]:
    detail_route = routes_by_title["库存明细统计"]
    outin_route = routes_by_title["出入库单据"]
    detail_page = resolve_page_research_record("库存明细统计", page_records)
    outin_page = resolve_page_research_record("出入库单据", page_records)
    detail_coverage = _coverage_metadata(resolve_menu_coverage_page("库存明细统计", menu_coverage_index))
    outin_coverage = _coverage_metadata(resolve_menu_coverage_page("出入库单据", menu_coverage_index))
    inventory_detail = dict((inventory_evidence.get("inventory_detail") or {}))
    outin_report = dict((inventory_evidence.get("outin_report") or {}))
    shared_sources = [_repo_path(inventory_evidence_path, repo_root)]
    if detail_page:
        shared_sources.append(detail_page["_source_path"])
    if outin_page:
        shared_sources.append(outin_page["_source_path"])
    if inventory_outin_research_path is not None:
        shared_sources.append(_repo_path(inventory_outin_research_path, repo_root))
    shared_sources = list(dict.fromkeys(shared_sources))

    detail_admission = dict((inventory_admission.get("inventory_detail") or {}))
    outin_admission = dict((inventory_admission.get("outin_report") or {}))
    stockflag_equivalence = dict((inventory_detail.get("stockflag_equivalence") or {}))
    page_interpretation = dict((((inventory_detail.get("parameter_semantics") or {}).get("page") or {}).get("interpretation") or {}))
    stockflag_values = list(detail_admission.get("recommended_stockflag_values") or [])
    detail_scope_notes = [f"stockflag={value}" for value in stockflag_values]
    if stockflag_equivalence.get("stockflag_1_equals_2"):
        detail_scope_notes.append("stockflag=2 等价于 stockflag=1")

    detail_entry = {
        "domain": "inventory",
        "domain_label": "库存",
        "route": "库存明细统计 / SelDeptStockWaitList",
        "title": "库存明细统计",
        "endpoint": detail_route["endpoint"],
        "role": "主源候选",
        "source_kind": "主源候选",
        "stage": "已HTTP回证",
        "trust_level": "中",
        "reliability_status": "中等可信",
        "coverage_scope": ["当前账号范围", "库存主源候选", *detail_scope_notes, "已完成 HTTP 回证"],
        "research_map_complete": True,
        "ingestion_blocked_by_global_gate": True,
        "mainline_ready": False,
        "blocking_issues": list(detail_admission.get("blocking_issues") or []),
        "next_action": (
            "库存明细统计已具备 capture 候选准入条件，按 stockflag=0/1 双范围留痕并固定 page=0"
            if detail_admission.get("capture_admission_ready")
            else "继续解释 page 语义或补充 scope 证据，再评估库存主源 capture 准入"
        ),
        "current_judgment": "库存事实源候选",
        "capture_strategy": "枚举 sweep",
        "risk_labels": detail_route["risk_labels"],
        "ledger_path": detail_route["ledger_path"],
        "analysis_sources": shared_sources,
        "capture_admission_ready": bool(detail_admission.get("capture_admission_ready")),
        "capture_parameter_plan": dict(detail_admission.get("capture_parameter_plan") or {}),
        "stockflag_equivalent_groups": list(detail_admission.get("stockflag_equivalent_groups") or []),
        "page_interpretation": page_interpretation,
        **detail_coverage,
    }

    outin_entry = {
        "domain": "inventory",
        "domain_label": "库存",
        "route": "出入库单据 / SelOutInStockReport",
        "title": "出入库单据",
        "endpoint": outin_route["endpoint"],
        "role": "主源候选",
        "source_kind": "主源候选",
        "stage": "已HTTP回证",
        "trust_level": "中",
        "reliability_status": "中等可信",
        "coverage_scope": [
            "当前账号范围",
            "库存单据主源候选",
            *(["datetype=" + "/".join(outin_admission.get("recommended_datetype_values") or [])] if outin_admission.get("recommended_datetype_values") else []),
            "已完成 HTTP 回证",
        ],
        "research_map_complete": True,
        "ingestion_blocked_by_global_gate": True,
        "mainline_ready": False,
        "blocking_issues": list(outin_admission.get("blocking_issues") or []),
        "next_action": (
            "按 datetype × type × doctype 的最小组合做正式 HTTP sweep，再评估库存单据 capture 准入"
            if not outin_admission.get("capture_admission_ready")
            else "库存单据已具备 capture 候选准入条件，按最小组合 sweep 进入批次留痕"
        ),
        "current_judgment": "库存单据主源候选",
        "capture_strategy": "枚举 sweep",
        "risk_labels": outin_route["risk_labels"],
        "ledger_path": outin_route["ledger_path"],
        "analysis_sources": shared_sources,
        "capture_admission_ready": bool(outin_admission.get("capture_admission_ready")),
        "capture_parameter_plan": dict(outin_admission.get("capture_parameter_plan") or {}),
        "recommended_type_values": list(outin_admission.get("recommended_type_values") or []),
        "recommended_doctype_values": list(outin_admission.get("recommended_doctype_values") or []),
        "doctype_equivalent_groups": list(outin_admission.get("doctype_equivalent_groups") or []),
        "parameter_semantics": dict(outin_report.get("parameter_semantics") or {}),
        **outin_coverage,
    }
    return [detail_entry, outin_entry]


def _build_member_evidence_entries(
    *,
    member_evidence: dict[str, Any],
    routes_by_title: dict[str, dict[str, Any]],
    page_records: dict[str, dict[str, Any]],
    menu_coverage_index: dict[str, dict[str, Any]],
    repo_root: Path,
    member_evidence_path: Path,
) -> list[dict[str, Any]]:
    member_route = routes_by_title["会员中心"]
    member_page = resolve_page_research_record("会员中心", page_records)
    member_coverage = _coverage_metadata(resolve_menu_coverage_page("会员中心", menu_coverage_index))
    member_center = dict((member_evidence.get("member_center") or {}))
    parameter_semantics = dict((member_center.get("parameter_semantics") or {}))
    condition_probe_summary = dict((member_center.get("condition_probe_summary") or {}))
    search_behavior = dict((member_center.get("search_behavior") or {}))
    analysis_sources = [_repo_path(member_evidence_path, repo_root)]
    if member_page:
        analysis_sources.append(member_page["_source_path"])
    analysis_sources = list(dict.fromkeys(analysis_sources))

    return [
        {
            "domain": "member",
            "domain_label": "会员",
            "route": "会员中心 / SelVipInfoList",
            "title": "会员中心",
            "endpoint": member_route["endpoint"],
            "role": "主源候选",
            "source_kind": "主源候选",
            "stage": "已HTTP回证",
            "trust_level": "中",
            "reliability_status": "中等可信",
            "coverage_scope": [
                "当前账号范围",
                "会员主数据候选",
                "默认空查询返回全量会员集合",
                "已完成 HTTP 回证",
            ],
            "research_map_complete": True,
            "ingestion_blocked_by_global_gate": True,
            "mainline_ready": bool(member_center.get("capture_admission_ready")),
            "blocking_issues": list(member_center.get("blocking_issues") or []),
            "next_action": (
                "会员中心已具备 capture 候选准入条件，按默认空条件单请求写入 member_profile_records，并继续跟进 condition / VolumeNumber 的非阻塞语义。"
                if bool(member_center.get("capture_admission_ready"))
                else "继续从页面控件或接口上下文反推 condition 合法值，并确认是否存在服务端上限，再评估 capture 准入"
            ),
            "current_judgment": "会员主数据候选源（默认空查询可直接返回会员集合，searchval 可用于全局过滤）",
            "capture_strategy": "单请求",
            "risk_labels": member_route["risk_labels"],
            "ledger_path": member_route["ledger_path"],
            "analysis_sources": analysis_sources,
            "capture_admission_ready": bool(member_center.get("capture_admission_ready")),
            "capture_parameter_plan": {
                "default_condition": "",
                "default_searchval": "",
                "default_VolumeNumber": "",
                "search_mode": "global_filter_when_condition_empty",
                "search_exact_examples": list(search_behavior.get("exact_match_values") or []),
                "volume_examples": [
                    item.get("value")
                    for item in (parameter_semantics.get("VolumeNumber") or {}).get("variants", [])
                ],
            },
            "parameter_semantics": parameter_semantics,
            "condition_probe_summary": condition_probe_summary,
            "search_behavior": search_behavior,
            **member_coverage,
        }
    ]


def _build_member_maintenance_evidence_entries(
    *,
    member_maintenance_evidence: dict[str, Any],
    routes_by_title: dict[str, dict[str, Any]],
    page_records: dict[str, dict[str, Any]],
    menu_coverage_index: dict[str, dict[str, Any]],
    repo_root: Path,
    member_maintenance_evidence_path: Path,
) -> list[dict[str, Any]]:
    maintenance_route = routes_by_title.get("会员维护")
    if maintenance_route is None:
        return []
    maintenance_page = resolve_page_research_record("会员维护", page_records)
    maintenance_coverage = _coverage_metadata(resolve_menu_coverage_page("会员维护", menu_coverage_index))
    maintenance = dict((member_maintenance_evidence.get("member_maintenance") or {}))
    parameter_semantics = dict((maintenance.get("parameter_semantics") or {}))
    analysis_sources = [_repo_path(member_maintenance_evidence_path, repo_root)]
    if maintenance_page:
        analysis_sources.append(maintenance_page["_source_path"])
    analysis_sources = list(dict.fromkeys(analysis_sources))

    capture_admission_ready = bool(maintenance.get("capture_admission_ready"))
    return [
        {
            "domain": "member",
            "domain_label": "会员",
            "route": "会员维护 / SelVipReturnVisitList",
            "title": "会员维护",
            "endpoint": maintenance_route["endpoint"],
            "role": "主源候选",
            "source_kind": "主源候选",
            "stage": "已HTTP回证",
            "trust_level": "中" if capture_admission_ready else "低",
            "reliability_status": "中等可信" if capture_admission_ready else "能跑但不能信",
            "coverage_scope": [
                "当前账号范围",
                "会员维护主列表候选",
                *(
                    ["当前账号稳定空集已验证"]
                    if capture_admission_ready
                    else ["当前 baseline 为空数据集"]
                ),
                "已完成 HTTP 回证",
            ],
            "research_map_complete": True,
            "ingestion_blocked_by_global_gate": False,
            "mainline_ready": capture_admission_ready,
            "blocking_issues": list(maintenance.get("blocking_issues") or []),
            "next_action": str(
                (member_maintenance_evidence.get("conclusion") or {}).get("next_focus")
                or "先确认当前账号是否真实无会员回访数据，或页面动作链是否会补充隐藏上下文"
            ),
            "current_judgment": str(
                maintenance.get("judgment")
                or "会员维护真实主接口已完成 HTTP 回证，但当前账号 baseline 为空。"
            ),
            "capture_strategy": maintenance_route["capture_strategy"],
            "risk_labels": maintenance_route["risk_labels"],
            "ledger_path": maintenance_route["ledger_path"],
            "analysis_sources": analysis_sources,
            "capture_admission_ready": capture_admission_ready,
            "capture_parameter_plan": dict(maintenance.get("capture_parameter_plan") or {}),
            "parameter_semantics": parameter_semantics,
            **maintenance_coverage,
        }
    ]


def _build_member_analysis_snapshot_entries(
    *,
    member_analysis_snapshot_evidence: dict[str, Any],
    routes_by_title: dict[str, dict[str, Any]],
    page_records: dict[str, dict[str, Any]],
    menu_coverage_index: dict[str, dict[str, Any]],
    repo_root: Path,
    member_analysis_snapshot_evidence_path: Path,
) -> list[dict[str, Any]]:
    route = routes_by_title.get("会员总和分析")
    if route is None:
        return []
    page_record = resolve_page_research_record("会员总和分析", page_records)
    coverage = _coverage_metadata(resolve_menu_coverage_page("会员总和分析", menu_coverage_index))
    snapshot_detail = dict((member_analysis_snapshot_evidence.get("member_analysis_snapshot") or {}))
    capture_admission_ready = bool(snapshot_detail.get("capture_admission_ready"))
    capture_page_summary = dict((snapshot_detail.get("capture_page_summary") or {}))
    analysis_sources = [_repo_path(member_analysis_snapshot_evidence_path, repo_root)]
    if page_record:
        analysis_sources.append(page_record["_source_path"])
    analysis_sources = list(dict.fromkeys(analysis_sources))

    scope_notes = ["当前账号范围", "会员分析结果快照", "page=0 当前为全量模式", "已完成 HTTP 回证"]
    type_semantics = dict((snapshot_detail.get("capture_parameter_plan") or {}).get("type_semantics") or {})
    tag_semantics = dict((snapshot_detail.get("capture_parameter_plan") or {}).get("tag_semantics") or {})
    if bool(type_semantics.get("same_dataset_for_tested_values")):
        scope_notes.append("type 已测值当前为同一数据集")
    if tag_semantics.get("different_dataset_values"):
        scope_notes.append("tag 会切结果子集")

    return [
        {
            "domain": "member",
            "domain_label": "会员",
            "route": "会员总和分析 / SelVipAnalysisReport",
            "title": "会员总和分析",
            "endpoint": route["endpoint"],
            "role": "结果快照",
            "source_kind": "结果快照",
            "stage": "已HTTP回证",
            "trust_level": "中" if capture_admission_ready else "低",
            "reliability_status": "中等可信" if capture_admission_ready else "能跑但不能信",
            "coverage_scope": scope_notes,
            "research_map_complete": True,
            "ingestion_blocked_by_global_gate": False,
            "mainline_ready": False,
            "blocking_issues": list(snapshot_detail.get("blocking_issues") or []),
            "next_action": (
                "会员总和分析已满足 snapshot capture 条件；按 page=0 单请求写入 capture，并继续保持结果快照定位。"
                if capture_admission_ready
                else "继续确认会员总和分析 page=0 全量模式与 type/tag 边界，再决定是否进入 snapshot capture。"
            ),
            "current_judgment": str(
                snapshot_detail.get("judgment")
                or "会员总和分析更像会员分析结果快照，适合作为 snapshot capture 留痕。"
            ),
            "capture_strategy": "单请求快照",
            "risk_labels": route["risk_labels"],
            "ledger_path": route["ledger_path"],
            "analysis_sources": analysis_sources,
            "capture_admission_ready": capture_admission_ready,
            "capture_parameter_plan": dict(snapshot_detail.get("capture_parameter_plan") or {}),
            "capture_page_summary": capture_page_summary,
            **coverage,
        }
    ]


def _build_product_evidence_entries(
    *,
    product_evidence: dict[str, Any],
    routes_by_title: dict[str, dict[str, Any]],
    page_records: dict[str, dict[str, Any]],
    menu_coverage_index: dict[str, dict[str, Any]],
    repo_root: Path,
    product_evidence_path: Path,
) -> list[dict[str, Any]]:
    product_route = routes_by_title.get("商品资料")
    if product_route is None:
        return []
    product_page = resolve_page_research_record("商品资料", page_records)
    product_coverage = _coverage_metadata(resolve_menu_coverage_page("商品资料", menu_coverage_index))
    product_list = dict((product_evidence.get("product_list") or {}))
    parameter_semantics = dict((product_list.get("parameter_semantics") or {}))
    pagesize_probe_summary = dict((product_list.get("pagesize_probe_summary") or {}))
    full_capture_probe_summary = dict((product_list.get("full_capture_probe_summary") or {}))
    search_behavior = dict((product_list.get("search_behavior") or {}))
    analysis_sources = [_repo_path(product_evidence_path, repo_root)]
    if product_page:
        analysis_sources.append(product_page["_source_path"])
    analysis_sources = list(dict.fromkeys(analysis_sources))

    capture_admission_ready = bool(product_list.get("capture_admission_ready"))
    return [
        {
            "domain": "sales",
            "domain_label": "销售",
            "route": "商品资料 / SelWareList",
            "title": "商品资料",
            "endpoint": product_route["endpoint"],
            "role": "主源候选",
            "source_kind": "主源候选",
            "stage": "已HTTP回证",
            "trust_level": "中",
            "reliability_status": "中等可信",
            "coverage_scope": [
                "当前账号范围",
                "商品主数据候选",
                "存在分页",
                "spenum 精确搜索可收敛",
                "已完成 HTTP 回证",
                *(
                    ["空 warecause 顺序翻页已验证全量抓取"]
                    if full_capture_probe_summary.get("verified_with_empty_warecause")
                    else []
                ),
            ],
            "research_map_complete": True,
            "ingestion_blocked_by_global_gate": False,
            "mainline_ready": capture_admission_ready,
            "blocking_issues": list(product_list.get("blocking_issues") or []),
            "next_action": (
                "按推荐大页尺寸顺序翻页进入正式 capture admit，并保留 warecause 为后续过滤语义研究项"
                if capture_admission_ready
                else "继续确认空 warecause 是否已覆盖当前账号全量商品数据"
            ),
            "current_judgment": (
                "商品主数据候选源（page 顺序翻页成立，spenum 支持搜索，空 warecause 已验证可覆盖当前账号全量数据）"
                if capture_admission_ready
                else "商品主数据候选源（page 顺序翻页成立，spenum 支持精确搜索）"
            ),
            "capture_strategy": "自动翻页",
            "risk_labels": product_route["risk_labels"],
            "ledger_path": product_route["ledger_path"],
            "analysis_sources": analysis_sources,
            "capture_admission_ready": capture_admission_ready,
            "capture_parameter_plan": dict(product_list.get("capture_parameter_plan") or {}),
            "parameter_semantics": parameter_semantics,
            "pagesize_probe_summary": pagesize_probe_summary,
            "full_capture_probe_summary": full_capture_probe_summary,
            "search_behavior": search_behavior,
            **product_coverage,
        }
    ]


def _build_product_sales_snapshot_entries(
    *,
    product_sales_snapshot_evidence: dict[str, Any],
    routes_by_title: dict[str, dict[str, Any]],
    page_records: dict[str, dict[str, Any]],
    menu_coverage_index: dict[str, dict[str, Any]],
    repo_root: Path,
    product_sales_snapshot_evidence_path: Path,
) -> list[dict[str, Any]]:
    route = routes_by_title.get("商品销售情况")
    if route is None:
        return []
    page_record = resolve_page_research_record("商品销售情况", page_records)
    coverage = _coverage_metadata(resolve_menu_coverage_page("商品销售情况", menu_coverage_index))
    snapshot_detail = dict((product_sales_snapshot_evidence.get("product_sales_snapshot") or {}))
    capture_admission_ready = bool(snapshot_detail.get("capture_admission_ready"))
    capture_page_summary = dict((snapshot_detail.get("capture_page_summary") or {}))
    analysis_sources = [_repo_path(product_sales_snapshot_evidence_path, repo_root)]
    if page_record:
        analysis_sources.append(page_record["_source_path"])
    analysis_sources = list(dict.fromkeys(analysis_sources))

    scope_notes = ["当前账号范围", "商品维度聚合结果快照", "单请求结果快照", "已完成 HTTP 回证"]
    if bool(capture_page_summary.get("capture_complete")):
        scope_notes.append("单请求返回行数已匹配服务端声明总数")

    return [
        {
            "domain": "sales",
            "domain_label": "销售",
            "route": "商品销售情况 / SelSaleReportData",
            "title": "商品销售情况",
            "endpoint": route["endpoint"],
            "role": "结果快照",
            "source_kind": "结果快照",
            "stage": "已HTTP回证",
            "trust_level": "中" if capture_admission_ready else "低",
            "reliability_status": "中等可信" if capture_admission_ready else "能跑但不能信",
            "coverage_scope": scope_notes,
            "research_map_complete": True,
            "ingestion_blocked_by_global_gate": False,
            "mainline_ready": False,
            "blocking_issues": list(snapshot_detail.get("blocking_issues") or []),
            "next_action": (
                "商品销售情况已满足 snapshot capture 条件；按默认时间窗单请求写入 capture，并继续保持结果快照定位。"
                if capture_admission_ready
                else "继续确认商品销售情况单请求是否完整覆盖服务端声明总数，再决定是否进入 snapshot capture。"
            ),
            "current_judgment": str(
                snapshot_detail.get("judgment")
                or "商品销售情况更像商品维度聚合结果快照，适合作为 snapshot capture 留痕。"
            ),
            "capture_strategy": "单请求快照",
            "risk_labels": route["risk_labels"],
            "ledger_path": route["ledger_path"],
            "analysis_sources": analysis_sources,
            "capture_admission_ready": capture_admission_ready,
            "capture_parameter_plan": dict(snapshot_detail.get("capture_parameter_plan") or {}),
            "capture_page_summary": capture_page_summary,
            **coverage,
        }
    ]


def _build_daily_payment_snapshot_entries(
    *,
    daily_payment_snapshot_evidence: dict[str, Any],
    routes_by_title: dict[str, dict[str, Any]],
    page_records: dict[str, dict[str, Any]],
    menu_coverage_index: dict[str, dict[str, Any]],
    repo_root: Path,
    daily_payment_snapshot_evidence_path: Path,
) -> list[dict[str, Any]]:
    route = routes_by_title.get("每日流水单")
    if route is None:
        return []
    page_record = resolve_page_research_record("每日流水单", page_records)
    coverage = _coverage_metadata(resolve_menu_coverage_page("每日流水单", menu_coverage_index))
    snapshot_detail = dict((daily_payment_snapshot_evidence.get("daily_payment_snapshot") or {}))
    capture_admission_ready = bool(snapshot_detail.get("capture_admission_ready"))
    capture_page_summary = dict((snapshot_detail.get("capture_page_summary") or {}))
    analysis_sources = [_repo_path(daily_payment_snapshot_evidence_path, repo_root)]
    if page_record:
        analysis_sources.append(page_record["_source_path"])
    analysis_sources = list(dict.fromkeys(analysis_sources))

    scope_notes = ["当前账号范围", "支付流水结果快照", "单请求结果快照", "已完成 HTTP 回证"]
    searchtype_semantics = dict((snapshot_detail.get("capture_parameter_plan") or {}).get("searchtype_semantics") or {})
    if bool(searchtype_semantics.get("same_dataset_for_tested_values")):
        scope_notes.append("SearchType 已验证为同一数据集")

    return [
        {
            "domain": "payment_and_docs",
            "domain_label": "流水单据",
            "route": "每日流水单 / SelectRetailDocPaymentSlip",
            "title": "每日流水单",
            "endpoint": route["endpoint"],
            "role": "结果快照",
            "source_kind": "结果快照",
            "stage": "已HTTP回证",
            "trust_level": "中" if capture_admission_ready else "低",
            "reliability_status": "中等可信" if capture_admission_ready else "能跑但不能信",
            "coverage_scope": scope_notes,
            "research_map_complete": True,
            "ingestion_blocked_by_global_gate": False,
            "mainline_ready": False,
            "blocking_issues": list(snapshot_detail.get("blocking_issues") or []),
            "next_action": (
                "每日流水单已满足 snapshot capture 条件；按默认窗口单请求写入 capture，并继续保持结果快照定位。"
                if capture_admission_ready
                else "继续确认每日流水单的 SearchType 与分页边界，再决定是否进入 snapshot capture。"
            ),
            "current_judgment": str(
                snapshot_detail.get("judgment")
                or "每日流水单更像支付流水结果快照，适合作为 snapshot capture 留痕。"
            ),
            "capture_strategy": "单请求快照",
            "risk_labels": route["risk_labels"],
            "ledger_path": route["ledger_path"],
            "analysis_sources": analysis_sources,
            "capture_admission_ready": capture_admission_ready,
            "capture_parameter_plan": dict(snapshot_detail.get("capture_parameter_plan") or {}),
            "capture_page_summary": capture_page_summary,
            **coverage,
        }
    ]


def _build_stored_value_card_summary_snapshot_entries(
    *,
    stored_value_card_summary_snapshot_evidence: dict[str, Any],
    routes_by_title: dict[str, dict[str, Any]],
    page_records: dict[str, dict[str, Any]],
    menu_coverage_index: dict[str, dict[str, Any]],
    repo_root: Path,
    stored_value_card_summary_snapshot_evidence_path: Path,
) -> list[dict[str, Any]]:
    route = routes_by_title.get("储值卡汇总")
    if route is None:
        return []
    page_record = resolve_page_research_record("储值卡汇总", page_records)
    coverage = _coverage_metadata(resolve_menu_coverage_page("储值卡汇总", menu_coverage_index))
    snapshot_detail = dict((stored_value_card_summary_snapshot_evidence.get("stored_value_card_summary_snapshot") or {}))
    capture_admission_ready = bool(snapshot_detail.get("capture_admission_ready"))
    capture_page_summary = dict((snapshot_detail.get("capture_page_summary") or {}))
    analysis_sources = [_repo_path(stored_value_card_summary_snapshot_evidence_path, repo_root)]
    if page_record:
        analysis_sources.append(page_record["_source_path"])
    analysis_sources = list(dict.fromkeys(analysis_sources))

    scope_notes = ["当前账号范围", "卡级储值汇总结果快照", "单请求结果快照", "已完成 HTTP 回证"]
    search_semantics = dict((snapshot_detail.get("capture_parameter_plan") or {}).get("search_semantics") or {})
    if search_semantics.get("different_dataset_values"):
        scope_notes.append("Search 已验证可以切结果子集")

    return [
        {
            "domain": "stored_value",
            "domain_label": "储值",
            "route": "储值卡汇总 / GetDIYReportData",
            "title": "储值卡汇总",
            "endpoint": route["endpoint"],
            "role": "结果快照",
            "source_kind": "结果快照",
            "stage": "已HTTP回证",
            "trust_level": "中" if capture_admission_ready else "低",
            "reliability_status": "中等可信" if capture_admission_ready else "能跑但不能信",
            "coverage_scope": scope_notes,
            "research_map_complete": True,
            "ingestion_blocked_by_global_gate": False,
            "mainline_ready": False,
            "blocking_issues": list(snapshot_detail.get("blocking_issues") or []),
            "next_action": (
                "储值卡汇总已满足 snapshot capture 条件；按默认 Search 空值单请求写入 capture，并继续保持卡级汇总快照定位。"
                if capture_admission_ready
                else "继续确认储值卡汇总的 page/pagesize 语义与 Search 子集边界，再决定是否进入 snapshot capture。"
            ),
            "current_judgment": str(
                snapshot_detail.get("judgment")
                or "储值卡汇总更像卡级汇总结果快照，适合作为 snapshot capture 留痕。"
            ),
            "capture_strategy": "单请求快照",
            "risk_labels": route["risk_labels"],
            "ledger_path": route["ledger_path"],
            "analysis_sources": analysis_sources,
            "capture_admission_ready": capture_admission_ready,
            "capture_parameter_plan": dict(snapshot_detail.get("capture_parameter_plan") or {}),
            "capture_page_summary": capture_page_summary,
            **coverage,
        }
    ]


def _build_stored_value_by_store_snapshot_entries(
    *,
    stored_value_by_store_snapshot_evidence: dict[str, Any],
    routes_by_title: dict[str, dict[str, Any]],
    page_records: dict[str, dict[str, Any]],
    menu_coverage_index: dict[str, dict[str, Any]],
    repo_root: Path,
    stored_value_by_store_snapshot_evidence_path: Path,
) -> list[dict[str, Any]]:
    route = routes_by_title.get("储值按店汇总")
    if route is None:
        return []
    page_record = resolve_page_research_record("储值按店汇总", page_records)
    coverage = _coverage_metadata(resolve_menu_coverage_page("储值按店汇总", menu_coverage_index))
    snapshot_detail = dict((stored_value_by_store_snapshot_evidence.get("stored_value_by_store_snapshot") or {}))
    capture_admission_ready = bool(snapshot_detail.get("capture_admission_ready"))
    capture_page_summary = dict((snapshot_detail.get("capture_page_summary") or {}))
    analysis_sources = [_repo_path(stored_value_by_store_snapshot_evidence_path, repo_root)]
    if page_record:
        analysis_sources.append(page_record["_source_path"])
    analysis_sources = list(dict.fromkeys(analysis_sources))

    scope_notes = ["当前账号范围", "门店级储值汇总结果快照", "单请求结果快照", "已完成 HTTP 回证"]

    return [
        {
            "domain": "stored_value",
            "domain_label": "储值",
            "route": "储值按店汇总 / GetDIYReportData",
            "title": "储值按店汇总",
            "endpoint": route["endpoint"],
            "role": "结果快照",
            "source_kind": "结果快照",
            "stage": "已HTTP回证",
            "trust_level": "中" if capture_admission_ready else "低",
            "reliability_status": "中等可信" if capture_admission_ready else "能跑但不能信",
            "coverage_scope": scope_notes,
            "research_map_complete": True,
            "ingestion_blocked_by_global_gate": False,
            "mainline_ready": False,
            "blocking_issues": list(snapshot_detail.get("blocking_issues") or []),
            "next_action": (
                "储值按店汇总已满足 snapshot capture 条件；按默认时间窗单请求写入 capture，并继续保持门店级汇总快照定位。"
                if capture_admission_ready
                else "继续确认储值按店汇总的 page/pagesize 语义，再决定是否进入 snapshot capture。"
            ),
            "current_judgment": str(
                snapshot_detail.get("judgment")
                or "储值按店汇总更像门店级汇总结果快照，适合作为 snapshot capture 留痕。"
            ),
            "capture_strategy": "单请求快照",
            "risk_labels": route["risk_labels"],
            "ledger_path": route["ledger_path"],
            "analysis_sources": analysis_sources,
            "capture_admission_ready": capture_admission_ready,
            "capture_parameter_plan": dict(snapshot_detail.get("capture_parameter_plan") or {}),
            "capture_page_summary": capture_page_summary,
            **coverage,
        }
    ]


def _build_member_sales_rank_snapshot_entries(
    *,
    member_sales_rank_snapshot_evidence: dict[str, Any],
    routes_by_title: dict[str, dict[str, Any]],
    page_records: dict[str, dict[str, Any]],
    menu_coverage_index: dict[str, dict[str, Any]],
    repo_root: Path,
    member_sales_rank_snapshot_evidence_path: Path,
) -> list[dict[str, Any]]:
    route = routes_by_title.get("会员消费排行")
    if route is None:
        return []
    page_record = resolve_page_research_record("会员消费排行", page_records)
    coverage = _coverage_metadata(resolve_menu_coverage_page("会员消费排行", menu_coverage_index))
    snapshot_detail = dict((member_sales_rank_snapshot_evidence.get("member_sales_rank_snapshot") or {}))
    capture_admission_ready = bool(snapshot_detail.get("capture_admission_ready"))
    capture_page_summary = dict((snapshot_detail.get("capture_page_summary") or {}))
    analysis_sources = [_repo_path(member_sales_rank_snapshot_evidence_path, repo_root)]
    if page_record:
        analysis_sources.append(page_record["_source_path"])
    analysis_sources = list(dict.fromkeys(analysis_sources))

    scope_notes = ["当前账号范围", "会员消费排行结果快照", "page=0 当前为全量模式", "已完成 HTTP 回证"]
    if bool(capture_page_summary.get("capture_complete")):
        scope_notes.append("单请求返回行数已匹配服务端声明总数")

    return [
        {
            "domain": "member",
            "domain_label": "会员",
            "route": "会员消费排行 / SelVipSaleRank",
            "title": "会员消费排行",
            "endpoint": route["endpoint"],
            "role": "结果快照",
            "source_kind": "结果快照",
            "stage": "已HTTP回证",
            "trust_level": "中" if capture_admission_ready else "低",
            "reliability_status": "中等可信" if capture_admission_ready else "能跑但不能信",
            "coverage_scope": scope_notes,
            "research_map_complete": True,
            "ingestion_blocked_by_global_gate": False,
            "mainline_ready": False,
            "blocking_issues": list(snapshot_detail.get("blocking_issues") or []),
            "next_action": (
                "会员消费排行已满足 snapshot capture 条件；按 page=0 单请求写入 capture，并继续保持排行快照定位。"
                if capture_admission_ready
                else "继续确认会员消费排行 page=0 全量模式与单请求覆盖完整性，再决定是否进入 snapshot capture。"
            ),
            "current_judgment": str(
                snapshot_detail.get("judgment")
                or "会员消费排行更像排行结果快照，适合作为 snapshot capture 留痕。"
            ),
            "capture_strategy": "单请求快照",
            "risk_labels": route["risk_labels"],
            "ledger_path": route["ledger_path"],
            "analysis_sources": analysis_sources,
            "capture_admission_ready": capture_admission_ready,
            "capture_parameter_plan": dict(snapshot_detail.get("capture_parameter_plan") or {}),
            "capture_page_summary": capture_page_summary,
            **coverage,
        }
    ]


def _build_customer_evidence_entries(
    *,
    customer_evidence: dict[str, Any],
    routes_by_title: dict[str, dict[str, Any]],
    page_records: dict[str, dict[str, Any]],
    menu_coverage_index: dict[str, dict[str, Any]],
    repo_root: Path,
    customer_evidence_path: Path,
) -> list[dict[str, Any]]:
    customer_route = routes_by_title.get("客户资料")
    if customer_route is None:
        return []
    customer_page = resolve_page_research_record("客户资料", page_records)
    customer_coverage = _coverage_metadata(resolve_menu_coverage_page("客户资料", menu_coverage_index))
    customer_list = dict((customer_evidence.get("customer_list") or {}))
    parameter_semantics = dict((customer_list.get("parameter_semantics") or {}))
    analysis_sources = [_repo_path(customer_evidence_path, repo_root)]
    if customer_page:
        analysis_sources.append(customer_page["_source_path"])
    analysis_sources = list(dict.fromkeys(analysis_sources))

    capture_admission_ready = bool(customer_list.get("capture_admission_ready"))
    return [
        {
            "domain": "sales",
            "domain_label": "销售",
            "route": "客户资料 / SelDeptList",
            "title": "客户资料",
            "endpoint": customer_route["endpoint"],
            "role": "主源候选",
            "source_kind": "主源候选",
            "stage": "已HTTP回证",
            "trust_level": "中" if capture_admission_ready else "低",
            "reliability_status": "中等可信" if capture_admission_ready else "能跑但不能信",
            "coverage_scope": [
                "当前账号范围",
                "客户主数据候选",
                *(
                    ["当前账号稳定空集已验证"]
                    if capture_admission_ready
                    else ["当前 baseline 为空数据集"]
                ),
                "已完成 HTTP 回证",
            ],
            "research_map_complete": True,
            "ingestion_blocked_by_global_gate": False,
            "mainline_ready": capture_admission_ready,
            "blocking_issues": list(customer_list.get("blocking_issues") or []),
            "next_action": str(
                (customer_evidence.get("conclusion") or {}).get("next_focus")
                or "先确认当前账号是否真实无客户资料，或页面动作链是否会补充隐藏上下文"
            ),
            "current_judgment": str(customer_list.get("judgment") or "客户主数据候选源，但当前账号 baseline 为空"),
            "capture_strategy": customer_route["capture_strategy"],
            "risk_labels": customer_route["risk_labels"],
            "ledger_path": customer_route["ledger_path"],
            "analysis_sources": analysis_sources,
            "capture_admission_ready": capture_admission_ready,
            "capture_parameter_plan": dict(customer_list.get("capture_parameter_plan") or {}),
            "parameter_semantics": parameter_semantics,
            **customer_coverage,
        }
    ]


def _build_stored_value_evidence_entries(
    *,
    stored_value_evidence: dict[str, Any],
    routes_by_title: dict[str, dict[str, Any]],
    page_records: dict[str, dict[str, Any]],
    menu_coverage_index: dict[str, dict[str, Any]],
    repo_root: Path,
    stored_value_evidence_path: Path,
) -> list[dict[str, Any]]:
    stored_value_route = routes_by_title.get("储值卡明细")
    if stored_value_route is None:
        return []
    stored_value_page = resolve_page_research_record("储值卡明细", page_records)
    stored_value_coverage = _coverage_metadata(resolve_menu_coverage_page("储值卡明细", menu_coverage_index))
    stored_value_detail = dict((stored_value_evidence.get("stored_value_detail") or {}))
    parameter_semantics = dict((stored_value_detail.get("parameter_semantics") or {}))
    analysis_sources = [_repo_path(stored_value_evidence_path, repo_root)]
    if stored_value_page:
        analysis_sources.append(stored_value_page["_source_path"])
    analysis_sources = list(dict.fromkeys(analysis_sources))

    return [
        {
            "domain": "stored_value",
            "domain_label": "储值",
            "route": "储值卡明细 / GetDIYReportData",
            "title": "储值卡明细",
            "endpoint": stored_value_route["endpoint"],
            "role": "主源候选",
            "source_kind": "主源候选",
            "stage": "已HTTP回证",
            "trust_level": "中",
            "reliability_status": "中等可信",
            "coverage_scope": [
                "当前账号范围",
                "储值流水明细候选",
                "默认空 Search 返回主集合",
                "已完成 HTTP 回证",
            ],
            "research_map_complete": True,
            "ingestion_blocked_by_global_gate": not bool(stored_value_detail.get("capture_admission_ready")),
            "mainline_ready": bool(stored_value_detail.get("capture_admission_ready")),
            "blocking_issues": list(stored_value_detail.get("blocking_issues") or []),
            "next_action": str(
                (stored_value_evidence.get("conclusion") or {}).get("next_focus")
                or "先按默认空 Search 留痕进入 capture research，并继续确认 Search 语义与隐藏分页上限"
            ),
            "current_judgment": str(
                stored_value_detail.get("judgment")
                or "储值卡明细已完成 HTTP 回证，当前最像储值流水明细主源候选。"
            ),
            "capture_strategy": stored_value_route["capture_strategy"],
            "risk_labels": stored_value_route["risk_labels"],
            "ledger_path": stored_value_route["ledger_path"],
            "analysis_sources": analysis_sources,
            "capture_admission_ready": bool(stored_value_detail.get("capture_admission_ready")),
            "capture_parameter_plan": dict(stored_value_detail.get("capture_parameter_plan") or {}),
            "parameter_semantics": parameter_semantics,
            "search_behavior": dict(stored_value_detail.get("search_behavior") or {}),
            **stored_value_coverage,
        }
    ]


def _build_store_stocktaking_secondary_entries(
    *,
    page_records: dict[str, dict[str, Any]],
    menu_coverage_index: dict[str, dict[str, Any]],
    repo_root: Path,
    store_stocktaking_ui_probe_path: Path | None,
    store_stocktaking_ui_probe: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if store_stocktaking_ui_probe_path is None or store_stocktaking_ui_probe is None:
        return []

    diff_probe = next(
        (
            item
            for item in store_stocktaking_ui_probe.get("component_method_probes") or []
            if item.get("key") == "component_method_getDiffData"
        ),
        None,
    )
    if not diff_probe:
        return []

    diff_snapshot = (((diff_probe.get("local_state_after") or {}).get("snapshot") or {}).get("orderDiffData") or {})
    summary_snapshot = (((diff_probe.get("local_state_after") or {}).get("snapshot") or {}).get("orderDiffHJData") or {})
    diff_rows = list(diff_snapshot.get("full_rows") or [])
    summary_rows = list(summary_snapshot.get("full_rows") or [])
    if not diff_rows:
        return []

    row_1_probe = next(
        (
            item
            for item in store_stocktaking_ui_probe.get("component_method_probes") or []
            if item.get("key") == "component_method_getDiffData_row_1"
        ),
        None,
    )
    row_2_probe = next(
        (
            item
            for item in store_stocktaking_ui_probe.get("component_method_probes") or []
            if item.get("key") == "component_method_getDiffData_row_2"
        ),
        None,
    )

    def _rows_after_probe(probe: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
        if not probe:
            return []
        snapshot = (((probe.get("local_state_after") or {}).get("snapshot") or {}).get(key) or {})
        return list(snapshot.get("full_rows") or [])

    row_1_diff_rows = _rows_after_probe(row_1_probe, "orderDiffData")
    row_2_diff_rows = _rows_after_probe(row_2_probe, "orderDiffData")

    blocking_issues = [
        "统计损溢当前更像本地派生数据，尚未确认独立 HTTP route",
        "尚未确认多单据场景下 orderDiffData 是否稳定",
    ]
    if row_1_probe and not row_1_diff_rows:
        blocking_issues.append("按行调用 getDiffData(row_1) 当前会把 diff 状态清空，尚未证明多行稳定")
    if row_2_probe and not (row_2_probe.get("component_invocation") or {}).get("selected_row"):
        blocking_issues.append("按行调用 getDiffData(row_2) 当前仍未拿到稳定选中行")

    stocktaking_page = resolve_page_research_record("门店盘点单", page_records)
    coverage = _coverage_metadata(resolve_menu_coverage_page("门店盘点单", menu_coverage_index))
    analysis_sources = [_repo_path(store_stocktaking_ui_probe_path, repo_root)]
    if stocktaking_page:
        analysis_sources.append(stocktaking_page["_source_path"])
    analysis_sources = list(dict.fromkeys(analysis_sources))

    return [
        {
            "domain": "payment_and_docs",
            "domain_label": "流水单据",
            "route": "门店盘点单 / store_stocktaking_diff_records",
            "title": "门店盘点单",
            "endpoint": "store_stocktaking_diff_records",
            "role": "研究留痕",
            "source_kind": "研究留痕",
            "stage": "已单变量",
            "trust_level": "中",
            "reliability_status": "中等可信",
            "coverage_scope": ["当前账号范围", "本地派生二级数据", "统计损溢", "研究留痕定位"],
            "research_map_complete": True,
            "ingestion_blocked_by_global_gate": True,
            "mainline_ready": False,
            "blocking_issues": blocking_issues,
            "next_action": "继续区分默认 getDiffData() 产出的损溢总表与按行 getDiffData(row) 的稳定性，再决定是否把本地损溢数据固定为长期二级 raw route。",
            "current_judgment": "默认 getDiffData() 已能稳定导出本地损溢总表，但按行 getDiffData(row) 的多行稳定性尚未证实，可先作为 research-capture 路线留痕。",
            "capture_strategy": "研究留痕",
            "risk_labels": ["本地派生数据", "二级动作链", "统计损溢"],
            "ledger_path": "docs/erp/payment-and-doc-ledger.md",
            "analysis_sources": analysis_sources,
            "capture_admission_ready": False,
            "capture_parameter_plan": {
                "trigger_method": "getDiffData(row)",
                "selected_row_required": True,
                "observed_order_diff_rows": len(diff_rows),
                "observed_order_diff_summary_rows": len(summary_rows),
                "multi_row_supported": bool(row_1_probe and row_1_diff_rows),
            },
            "observed_local_secondary_state": {
                "order_diff_rows": len(diff_rows),
                "order_diff_summary_rows": len(summary_rows),
                "show_diff_page": bool(diff_snapshot.get("showDiffPage")),
                "row_1_order_diff_rows": len(row_1_diff_rows) if row_1_probe else None,
                "row_2_order_diff_rows": len(row_2_diff_rows) if row_2_probe else None,
            },
            **coverage,
        }
    ]


def _build_unknown_page_entries(
    menu_coverage_payload: dict[str, Any] | None,
    *,
    repo_root: Path,
    menu_coverage_path: Path | None,
    page_records: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not menu_coverage_payload:
        return []
    analysis_source = _repo_path(menu_coverage_path, repo_root) if menu_coverage_path else None
    entries: list[dict[str, Any]] = []
    page_records = page_records or {}
    for page in menu_coverage_payload.get("pages", []):
        if str(page.get("coverage_status") or "") != "visible_but_untracked":
            continue
        title = str(page.get("title") or "")
        if resolve_page_research_record(title, page_records):
            continue
        domain, domain_label = infer_domain_from_menu_metadata(
            str(page.get("root_name") or ""),
            str(page.get("group_name") or ""),
            title,
        )
        entries.append(
            {
                "domain": domain,
                "domain_label": domain_label,
                "route": f"{title} / unknown_page_needs_baseline",
                "title": title,
                "endpoint": "",
                "role": "待识别",
                "source_kind": "待识别",
                "stage": "已发现",
                "trust_level": "低",
                "reliability_status": "能跑但不能信",
                "coverage_scope": ["当前账号范围", "可见但未入板"],
                "research_map_complete": False,
                "ingestion_blocked_by_global_gate": True,
                "mainline_ready": False,
                "blocking_issues": ["当前账号可见页面尚未纳入研究台账基线"],
                "next_action": f"先补 {page.get('title')} 的页面基线研究，并识别主接口与过滤条件",
                "current_judgment": "当前账号可见页面，尚未纳入研究台账",
                "capture_strategy": "待识别",
                "risk_labels": ["待识别页面"],
                "ledger_path": "",
                "analysis_sources": [analysis_source] if analysis_source else [],
                **_coverage_metadata(page),
            }
        )
    return entries


def _with_capture_runtime(
    entries: list[dict[str, Any]],
    capture_runtime_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for entry in entries:
        runtime = capture_runtime_index.get(entry["route"]) or {}
        enriched_entry = dict(entry)
        enriched_entry["capture_written_once"] = bool(runtime.get("capture_written_once"))
        enriched_entry["latest_capture_batch_id"] = runtime.get("latest_capture_batch_id")
        enriched_entry["latest_capture_mode"] = runtime.get("latest_capture_mode")
        enriched_entry["latest_capture_artifact"] = runtime.get("latest_capture_artifact")
        enriched_entry["latest_capture_source_endpoint"] = runtime.get("latest_capture_source_endpoint")
        if (
            enriched_entry.get("capture_admission_ready")
            and enriched_entry.get("latest_capture_mode") == "admission"
            and enriched_entry.get("source_kind") == "主源候选"
        ):
            enriched_entry["mainline_ready"] = True
            if not (enriched_entry.get("secondary_route_blocking_issues") or []):
                enriched_entry["next_action"] = (
                    "已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。"
                )
        enriched.append(enriched_entry)
    return enriched


def _infer_dynamic_route_source_kind(
    *,
    title: str,
    root_name: str,
    group_name: str,
    page_record: dict[str, Any],
) -> str:
    joined = " ".join(filter(None, [root_name, group_name, title]))
    source_candidates = list(page_record.get("source_candidates") or [])
    result_candidates = list(page_record.get("result_snapshot_candidates") or [])
    if title in SETTINGS_PAGE_TITLES or any(token in joined for token in ("设置", "定位")):
        return "未采纳"
    if any(token in joined for token in ("资料", "维护")):
        return "主源候选"
    if any(token in joined for token in ("明细", "确认", "盘点")):
        return "主源候选"
    if source_candidates:
        return "主源候选"
    if result_candidates:
        return "结果快照"
    return "待识别"


def _page_stage_from_record(page_record: dict[str, Any]) -> str:
    return "已单变量" if page_record.get("single_variable_probe_results") else "已基线"


def _capture_strategy_from_page_record(source_kind: str, page_record: dict[str, Any]) -> str:
    if source_kind == "未采纳":
        return "暂不采纳"
    if source_kind == "结果快照":
        return "结果快照"
    strategy = str(page_record.get("recommended_capture_strategy") or "")
    mapping = {
        "baseline_single_request": "单请求",
        "http_followup_with_pagination": "自动翻页",
        "http_followup_with_enum_probe": "枚举 sweep",
        "http_followup_with_pagination_and_enum": "自动翻页 + 枚举 sweep",
        "split_head_and_line_routes": "分头行路线",
    }
    return mapping.get(strategy, "待识别")


def _coverage_scope_from_page_record(source_kind: str, page_record: dict[str, Any]) -> list[str]:
    tags = ["当前账号范围"]
    grain_route = str(page_record.get("grain_route") or "")
    if grain_route == "multi_grain_route":
        tags.append("多粒度")
    elif grain_route == "enum_or_scope_route":
        tags.append("存在范围或枚举切换")
    elif grain_route == "single_route":
        tags.append("单路线")
    hints = page_record.get("payload_hints") or {}
    if hints.get("pagination_fields"):
        tags.append("存在分页")
    if hints.get("enum_fields"):
        tags.append("存在枚举")
    if source_kind == "结果快照":
        tags.append("结果快照定位")
    if source_kind == "未采纳":
        tags.append("配置页面")
    return tags


def _dynamic_route_judgment_and_blockers(
    *,
    title: str,
    source_kind: str,
    page_record: dict[str, Any],
) -> tuple[str, list[str], str]:
    source_candidates = list(page_record.get("source_candidates") or [])
    hints = page_record.get("payload_hints") or {}
    if source_kind == "未采纳":
        return (
            "配置/设置页，默认不作为事实主源",
            ["配置/设置类页面，默认不进入事实主链"],
            f"保持 {title} 为未采纳；若后续确认有长期分析价值，再单独评估 snapshot 路线",
        )
    if source_kind == "结果快照":
        blockers = ["当前更像结果快照或页面配置返回，不作为事实主源"]
        if hints.get("pagination_fields"):
            blockers.append("分页语义仍待确认")
        if hints.get("enum_fields"):
            blockers.append("枚举/范围参数仍待确认")
        return (
            "当前更像结果快照或页面配置返回",
            blockers,
            f"先确认 {title} 是否只保留结果快照定位，再决定是否需要 snapshot capture",
        )
    blockers: list[str] = []
    if not source_candidates:
        blockers.append("页面基线尚未暴露稳定主接口")
    blockers.append("尚未完成纯 HTTP 回证")
    if hints.get("pagination_fields"):
        blockers.append("分页语义仍待确认")
    if hints.get("enum_fields"):
        blockers.append("枚举/范围参数仍待确认")
    if any(token in title for token in ("资料", "维护")):
        judgment = "当前更像主数据页，已完成页面基线"
        next_action = f"补 {title} 的纯 HTTP 回证，并确认过滤条件与分页语义"
    else:
        judgment = "当前更像业务明细或单据页，已完成页面基线"
        next_action = f"补 {title} 的主接口语义和纯 HTTP 回证，再评估是否进入主链候选"
    return judgment, blockers, next_action


def _build_researched_unknown_page_entries(
    *,
    page_records: dict[str, dict[str, Any]],
    menu_coverage_index: dict[str, dict[str, Any]],
    known_titles: set[str],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for title, page_record in sorted(page_records.items()):
        if title in known_titles:
            continue
        coverage_page = resolve_menu_coverage_page(title, menu_coverage_index)
        if not coverage_page:
            continue
        if list(coverage_page.get("matched_registry_titles") or []):
            continue
        root_name = str(coverage_page.get("root_name") or "")
        group_name = str(coverage_page.get("group_name") or "")
        domain, domain_label = infer_domain_from_menu_metadata(root_name, group_name, title)
        source_kind = _infer_dynamic_route_source_kind(
            title=title,
            root_name=root_name,
            group_name=group_name,
            page_record=page_record,
        )
        stage = _page_stage_from_record(page_record)
        current_judgment, blocking_issues, next_action = _dynamic_route_judgment_and_blockers(
            title=title,
            source_kind=source_kind,
            page_record=page_record,
        )
        trust_level = _default_trust(stage, source_kind, bool(blocking_issues))
        coverage = _coverage_metadata(coverage_page)
        source_candidates = list(page_record.get("source_candidates") or [])
        result_candidates = list(page_record.get("result_snapshot_candidates") or [])
        endpoint = source_candidates[0] if source_candidates else (result_candidates[0] if result_candidates else "")
        route = f"{title} / {endpoint or 'page_baseline'}"
        entries.append(
            {
                "domain": domain,
                "domain_label": domain_label,
                "route": route,
                "title": title,
                "endpoint": endpoint,
                "role": source_kind,
                "source_kind": source_kind,
                "stage": stage,
                "trust_level": trust_level,
                "reliability_status": "能跑但不能信" if trust_level == "低" else ("中等可信" if trust_level == "中" else "高可信"),
                "coverage_scope": _coverage_scope_from_page_record(source_kind, page_record),
                "research_map_complete": True,
                "ingestion_blocked_by_global_gate": True,
                "mainline_ready": False,
                "blocking_issues": blocking_issues,
                "next_action": next_action,
                "current_judgment": current_judgment,
                "capture_strategy": _capture_strategy_from_page_record(source_kind, page_record),
                "risk_labels": list(dict.fromkeys([
                    *(["需要翻页"] if (page_record.get("payload_hints") or {}).get("pagination_fields") else []),
                    *(["需要扫枚举"] if (page_record.get("payload_hints") or {}).get("enum_fields") else []),
                    *(["主接口待识别"] if not source_candidates and source_kind == "主源候选" else []),
                    *(["结果快照"] if source_kind == "结果快照" else []),
                    *(["配置页面"] if source_kind == "未采纳" else []),
                ])),
                "ledger_path": "",
                "analysis_sources": [page_record["_source_path"]],
                **coverage,
            }
        )
    return entries


def _build_route_entries(
    *,
    repo_root: Path,
    analysis_root: Path,
) -> tuple[list[dict[str, Any]], BoardSourceFiles]:
    ledger_routes = load_ledger_routes(repo_root)
    routes_by_title = {item["title"]: item for item in ledger_routes}
    known_titles = set(routes_by_title)
    page_records, page_files = load_best_page_research(repo_root, analysis_root)
    report_matrix_path, _ = load_report_matrix(analysis_root)
    sales_evidence_path, sales_evidence = load_sales_evidence(analysis_root)
    inventory_evidence_path, inventory_evidence = load_inventory_evidence(analysis_root)
    store_stocktaking_evidence_path, store_stocktaking_evidence = load_store_stocktaking_evidence(analysis_root)
    store_stocktaking_ui_probe_path, store_stocktaking_ui_probe = load_store_stocktaking_ui_probe(analysis_root)
    return_detail_evidence_path, return_detail_evidence = load_return_detail_evidence(analysis_root)
    return_detail_ui_probe_path, return_detail_ui_probe = load_return_detail_ui_probe(analysis_root)
    receipt_confirmation_evidence_path, receipt_confirmation_evidence = load_receipt_confirmation_evidence(analysis_root)
    receipt_confirmation_ui_probe_path, receipt_confirmation_ui_probe = load_receipt_confirmation_ui_probe(analysis_root)
    member_evidence_path, member_evidence = load_member_evidence(analysis_root)
    member_maintenance_evidence_path, member_maintenance_evidence = load_member_maintenance_evidence(analysis_root)
    member_analysis_snapshot_evidence_path, member_analysis_snapshot_evidence = load_member_analysis_snapshot_evidence(analysis_root)
    member_sales_rank_snapshot_evidence_path, member_sales_rank_snapshot_evidence = load_member_sales_rank_snapshot_evidence(analysis_root)
    product_evidence_path, product_evidence = load_product_evidence(analysis_root)
    product_sales_snapshot_evidence_path, product_sales_snapshot_evidence = load_product_sales_snapshot_evidence(analysis_root)
    daily_payment_snapshot_evidence_path, daily_payment_snapshot_evidence = load_daily_payment_snapshot_evidence(analysis_root)
    stored_value_card_summary_snapshot_evidence_path, stored_value_card_summary_snapshot_evidence = load_stored_value_card_summary_snapshot_evidence(analysis_root)
    stored_value_by_store_snapshot_evidence_path, stored_value_by_store_snapshot_evidence = load_stored_value_by_store_snapshot_evidence(analysis_root)
    customer_evidence_path, customer_evidence = load_customer_evidence(analysis_root)
    stored_value_evidence_path, stored_value_evidence = load_stored_value_evidence(analysis_root)
    inventory_outin_research_path, inventory_outin_research = load_inventory_outin_research(analysis_root)
    capture_runtime_index, capture_runtime_files = load_capture_runtime_state(repo_root, analysis_root)
    outin_research_sweep_summary = (
        (((inventory_outin_research or {}).get("summary") or {}).get("outin_report") or {}).get("research_sweep_summary")
        or {}
    )
    inventory_admission = (
        build_inventory_capture_admission_bundle(
            inventory_evidence=inventory_evidence,
            outin_research_sweep_summary=outin_research_sweep_summary,
        )
        if inventory_evidence_path is not None and inventory_evidence is not None
        else None
    )
    menu_coverage_path, menu_coverage_payload = load_latest_menu_coverage_audit(analysis_root)
    menu_coverage_index = _build_menu_coverage_index(menu_coverage_payload)

    entries: list[dict[str, Any]] = []
    has_sales_evidence = sales_evidence is not None and sales_evidence_path is not None
    for route in ledger_routes:
        if route["title"] == "销售清单":
            continue
        if has_sales_evidence and route["title"] == "零售明细统计":
            continue
        if inventory_admission is not None and route["title"] in {"库存明细统计", "出入库单据"}:
            continue
        if member_evidence is not None and member_evidence_path is not None and route["title"] == "会员中心":
            continue
        if member_maintenance_evidence is not None and member_maintenance_evidence_path is not None and route["title"] == "会员维护":
            continue
        if (
            member_analysis_snapshot_evidence is not None
            and member_analysis_snapshot_evidence_path is not None
            and route["title"] == "会员总和分析"
        ):
            continue
        if (
            member_sales_rank_snapshot_evidence is not None
            and member_sales_rank_snapshot_evidence_path is not None
            and route["title"] == "会员消费排行"
        ):
            continue
        if product_evidence is not None and product_evidence_path is not None and route["title"] == "商品资料":
            continue
        if (
            product_sales_snapshot_evidence is not None
            and product_sales_snapshot_evidence_path is not None
            and route["title"] == "商品销售情况"
        ):
            continue
        if (
            daily_payment_snapshot_evidence is not None
            and daily_payment_snapshot_evidence_path is not None
            and route["title"] == "每日流水单"
        ):
            continue
        if (
            stored_value_card_summary_snapshot_evidence is not None
            and stored_value_card_summary_snapshot_evidence_path is not None
            and route["title"] == "储值卡汇总"
        ):
            continue
        if (
            stored_value_by_store_snapshot_evidence is not None
            and stored_value_by_store_snapshot_evidence_path is not None
            and route["title"] == "储值按店汇总"
        ):
            continue
        if customer_evidence is not None and customer_evidence_path is not None and route["title"] == "客户资料":
            continue
        if stored_value_evidence is not None and stored_value_evidence_path is not None and route["title"] == "储值卡明细":
            continue
        page_record = resolve_page_research_record(route["title"], page_records)
        coverage_page = resolve_menu_coverage_page(route["title"], menu_coverage_index)
        entry = _build_generic_entry(route, page_record, coverage_page)
        if route["title"] == "会员中心":
            entry["blocking_issues"] = [
                "condition / searchval / VolumeNumber 语义仍待确认",
                "尚未完成纯 HTTP 回证",
            ]
            entry["next_action"] = "补 condition / searchval / VolumeNumber 的单变量与 HTTP 回证"
        elif route["title"] == "储值卡明细":
            entry["blocking_issues"] = [
                "Search 语义仍待确认",
                "尚未确认是否存在隐藏分页或服务端上限",
            ]
            entry["next_action"] = "先补 Search 语义与分页上限验证，再评估储值域主源准入"
        elif route["title"] == "每日流水单":
            entry["blocking_issues"] = [
                "SearchType 的完整枚举未确认",
                "尚未确认是否存在分页或数量限制",
            ]
            entry["next_action"] = "补 SearchType 枚举和分页限制研究，保持结果快照定位"
        elif route["title"] == "退货明细":
            if return_detail_evidence is not None and return_detail_evidence_path is not None:
                detail = return_detail_evidence.get("return_detail") or {}
                entry["stage"] = "已HTTP回证"
                entry["trust_level"] = "低"
                entry["reliability_status"] = "能跑但不能信"
                entry["blocking_issues"] = list(detail.get("blocking_issues") or [])
                entry["next_action"] = str((return_detail_evidence.get("conclusion") or {}).get("next_focus") or entry["next_action"])
                entry["current_judgment"] = str(detail.get("judgment") or entry["current_judgment"])
                entry["analysis_sources"] = list(
                    dict.fromkeys([*entry["analysis_sources"], _repo_path(return_detail_evidence_path, repo_root)])
                )
                entry["capture_parameter_plan"] = dict(detail.get("capture_parameter_plan") or {})
                type_probe_summary = detail.get("type_probe_summary") or {}
                tested_values = {str(item) for item in type_probe_summary.get("tested_values") or []}
                successful_values = {str(item) for item in type_probe_summary.get("successful_values") or []}
                filter_coverage = detail.get("base_info_filter_coverage") or {}
                if (
                    {"4", "5"} <= tested_values
                    and not successful_values
                    and "已补测祖先状态暴露的 type=4/5 候选值，仍全部触发服务端错误" not in entry["blocking_issues"]
                ):
                    entry["blocking_issues"].append("已补测祖先状态暴露的 type=4/5 候选值，仍全部触发服务端错误")
                if (
                    filter_coverage.get("mapping_complete") is True
                    and "ReturnStockBaseInfo 当前 11 个可见筛选维度都已纳入 probe，问题已不在可见筛选遗漏" not in entry["blocking_issues"]
                ):
                    entry["blocking_issues"].append(
                        "ReturnStockBaseInfo 当前 11 个可见筛选维度都已纳入 probe，问题已不在可见筛选遗漏"
                    )
                if return_detail_ui_probe is not None and return_detail_ui_probe_path is not None:
                    entry["analysis_sources"] = list(
                        dict.fromkeys([*entry["analysis_sources"], _repo_path(return_detail_ui_probe_path, repo_root)])
                    )
                    baseline_payload = ((return_detail_ui_probe.get("baseline") or {}).get("return_detail_post_data")) or {}
                    baseline_ancestry_ref_states = (
                        ((return_detail_ui_probe.get("baseline") or {}).get("component_ancestry_ref_states_after_query"))
                        or []
                    )
                    probe_payloads = [
                        probe.get("return_detail_post_data")
                        for probe in return_detail_ui_probe.get("probes") or []
                        if probe.get("return_detail_post_data") is not None
                    ]
                    static_payload = bool(probe_payloads) and all(payload == baseline_payload for payload in probe_payloads)
                    filter_keys = {
                        "TradeMarkCode",
                        "Years",
                        "Season",
                        "TypeCode",
                        "State",
                        "PlatId",
                        "Order",
                        "ArriveStore",
                        "Style",
                    }
                    diagnostics = ((return_detail_ui_probe.get("baseline") or {}).get("component_diagnostics_after_query")) or []
                    method_owner_candidates = (
                        ((return_detail_ui_probe.get("baseline") or {}).get("method_owner_candidates_after_query")) or []
                    )
                    page_component_state = (
                        ((return_detail_ui_probe.get("baseline") or {}).get("page_component_state_after_query")) or {}
                    )
                    refs_snapshot = (page_component_state.get("refs_snapshot") or {}) if isinstance(page_component_state, dict) else {}
                    exposed_filter_model = False
                    for item in diagnostics:
                        matched = set(item.get("matched_keys") or [])
                        nested = {
                            child_key
                            for nested_match in item.get("nested_matches") or []
                            for child_key in nested_match.get("child_keys") or []
                        }
                        if matched & filter_keys or nested & filter_keys:
                            exposed_filter_model = True
                            break
                    if static_payload and "页面真实点击后的查询请求仍未改变 post body" not in entry["blocking_issues"]:
                        entry["blocking_issues"].append("页面真实点击后的查询请求仍未改变 post body")
                    if not exposed_filter_model and "组件诊断仍未暴露 route-level 过滤模型" not in entry["blocking_issues"]:
                        entry["blocking_issues"].append("组件诊断仍未暴露 route-level 过滤模型")
                    if method_owner_candidates:
                        method_probe_steps = [
                            probe.get("component_method_step")
                            for probe in return_detail_ui_probe.get("probes") or []
                            if str(probe.get("label") or "").startswith("component_method:")
                        ]
                        no_request_methods = [
                            str((step or {}).get("key") or "")
                            for step in method_probe_steps
                            if not ((step or {}).get("request_delta") or {}).get("requests")
                        ]
                        if (
                            no_request_methods
                            and "已定位 RTM_searchConditions/RTM_getReportInfo，但调用后仍未触发新请求" not in entry["blocking_issues"]
                        ):
                            entry["blocking_issues"].append("已定位 RTM_searchConditions/RTM_getReportInfo，但调用后仍未触发新请求")
                    report_table_ref = refs_snapshot.get("RTM_reportTable") if isinstance(refs_snapshot, dict) else None
                    report_table_snapshot = (report_table_ref or {}).get("snapshot") if isinstance(report_table_ref, dict) else {}
                    report_table_nested = (
                        (report_table_ref or {}).get("nested_snapshots") if isinstance(report_table_ref, dict) else {}
                    )
                    report_table_special = (
                        (report_table_ref or {}).get("special_snapshot") if isinstance(report_table_ref, dict) else {}
                    )
                    if (
                        report_table_ref
                        and report_table_snapshot
                        and all(
                            isinstance(value, dict) and value.get("type") == "function"
                            for value in report_table_snapshot.values()
                        )
                        and isinstance(report_table_nested, dict)
                        and "vxeTable" in report_table_nested
                        and "RTM_reportTable 目前只暴露方法与 vxeTable 空条件状态，仍未看到可写筛选模型" not in entry["blocking_issues"]
                    ):
                        entry["blocking_issues"].append(
                            "RTM_reportTable 目前只暴露方法与 vxeTable 空条件状态，仍未看到可写筛选模型"
                        )
                    safe_method_sources = (page_component_state or {}).get("safe_method_sources") or {}
                    if (
                        safe_method_sources
                        and all(str((item or {}).get("preview") or "").endswith("[native code] }") for item in safe_method_sources.values())
                        and "RTM_searchConditions/RTM_getReportInfo 当前只暴露 native code 包装，仍无法从函数体反推出隐藏上下文" not in entry["blocking_issues"]
                    ):
                        entry["blocking_issues"].append(
                            "RTM_searchConditions/RTM_getReportInfo 当前只暴露 native code 包装，仍无法从函数体反推出隐藏上下文"
                        )
                    table_ref_indexeddb = ((return_detail_ui_probe.get("baseline") or {}).get("table_ref_indexeddb_after_query")) or {}
                    target_database = table_ref_indexeddb.get("target_database") if isinstance(table_ref_indexeddb, dict) else {}
                    object_store_names = target_database.get("object_store_names") if isinstance(target_database, dict) else None
                    if (
                        isinstance(report_table_special, dict)
                        and report_table_special.get("vxeTable_snapshot")
                        and "RTM_reportTable.vxeTable.database 已指向 FXDATABASE，但浏览器实际打开后 object_store_names 为空，salesReturnDetailReport 并未落成本地表"
                        not in entry["blocking_issues"]
                        and isinstance(object_store_names, list)
                        and not object_store_names
                    ):
                        entry["blocking_issues"].append(
                            "RTM_reportTable.vxeTable.database 已指向 FXDATABASE，但浏览器实际打开后 object_store_names 为空，salesReturnDetailReport 并未落成本地表"
                        )
                    ref_method_sources = return_detail_ui_probe.get("ref_method_sources") or []
                    if ref_method_sources:
                        methods = (ref_method_sources[0] or {}).get("methods") or {}
                        if (
                            methods
                            and all("[native code]" in str((meta or {}).get("preview") or "") for meta in methods.values())
                            and "RTM_reportTable.searchConditions/searchDataInfo/pageCondition/getReportInfo/conditionStr 当前都只暴露 native code 包装"
                            not in entry["blocking_issues"]
                        ):
                            entry["blocking_issues"].append(
                                "RTM_reportTable.searchConditions/searchDataInfo/pageCondition/getReportInfo/conditionStr 当前都只暴露 native code 包装"
                            )
                    ancestry_method_sources = ((return_detail_ui_probe.get("baseline") or {}).get("component_ancestry_method_sources_after_query")) or []
                    if ancestry_method_sources:
                        ancestry_depth_0 = next(
                            (item for item in ancestry_method_sources if int(item.get("depth") or 0) == 0),
                            None,
                        )
                        ancestry_depth_1 = next(
                            (item for item in ancestry_method_sources if int(item.get("depth") or 0) == 1),
                            None,
                        )
                        depth_0_methods = (ancestry_depth_0 or {}).get("methods") or []
                        depth_1_methods = (ancestry_depth_1 or {}).get("methods") or []
                        if (
                            depth_0_methods
                            and all("[native code]" in str((item or {}).get("preview") or "") for item in depth_0_methods)
                            and "salesReturnDetailReport 根组件的查询/加载方法当前也只暴露 native code 包装，无法继续从根组件函数体反推上下文注入链" not in entry["blocking_issues"]
                        ):
                            entry["blocking_issues"].append(
                                "salesReturnDetailReport 根组件的查询/加载方法当前也只暴露 native code 包装，无法继续从根组件函数体反推上下文注入链"
                            )
                        if (
                            depth_1_methods
                            and all("[native code]" in str((item or {}).get("preview") or "") for item in depth_1_methods)
                            and "salesReturnDetailReport 父链壳层方法当前也只暴露 native code 包装，说明更早的菜单/页面注入链同样不可从函数体继续回溯" not in entry["blocking_issues"]
                        ):
                            entry["blocking_issues"].append(
                                "salesReturnDetailReport 父链壳层方法当前也只暴露 native code 包装，说明更早的菜单/页面注入链同样不可从函数体继续回溯"
                            )
                    self_ref = next(
                        (
                            item
                            for item in baseline_ancestry_ref_states
                            if str(item.get("ref_name") or "") == "salesReturnDetail"
                        ),
                        None,
                    )
                    navmenu_ref = next(
                        (
                            item
                            for item in baseline_ancestry_ref_states
                            if str(item.get("ref_name") or "") == "navmenu"
                        ),
                        None,
                    )
                    if (
                        self_ref
                        and navmenu_ref
                        and str(self_ref.get("component_name") or "") == "salesReturnDetail"
                        and set(navmenu_ref.get("matched_keys") or []) == set()
                        and set(navmenu_ref.get("props_data_keys") or []) == set()
                        and "salesReturnDetail 自身 ref 当前只拿到 showLoading 回调，父链 navmenu 也未见任何附加数据载荷，说明壳层 ref 仍不是缺失退货数据的来源" not in entry["blocking_issues"]
                    ):
                        entry["blocking_issues"].append(
                            "salesReturnDetail 自身 ref 当前只拿到 showLoading 回调，父链 navmenu 也未见任何附加数据载荷，说明壳层 ref 仍不是缺失退货数据的来源"
                        )
                    store_state_after = ((return_detail_ui_probe.get("baseline") or {}).get("component_store_state_after_query")) or {}
                    store_state_snapshot = (store_state_after.get("store_state_snapshot") or {}) if isinstance(store_state_after, dict) else {}
                    root_data_snapshot = (store_state_after.get("root_data_snapshot") or {}) if isinstance(store_state_after, dict) else {}
                    if (
                        store_state_snapshot == {"cleardata": False}
                        and root_data_snapshot == {}
                        and "store/root 当前只见 cleardata=false 与空 root_data_snapshot，仍未见任何退货数据缓存" not in entry["blocking_issues"]
                    ):
                        entry["blocking_issues"].append(
                            "store/root 当前只见 cleardata=false 与空 root_data_snapshot，仍未见任何退货数据缓存"
                        )
                    global_storage_after = (
                        ((return_detail_ui_probe.get("baseline") or {}).get("component_global_storage_after_query")) or {}
                    )
                    local_storage_entries = (
                        (global_storage_after.get("local_storage_entries") or [])
                        if isinstance(global_storage_after, dict)
                        else []
                    )
                    session_storage_entries = (
                        (global_storage_after.get("session_storage_entries") or [])
                        if isinstance(global_storage_after, dict)
                        else []
                    )
                    vm_inject_snapshot = (
                        (global_storage_after.get("vm_inject_snapshot") or {})
                        if isinstance(global_storage_after, dict)
                        else {}
                    )
                    if (
                        len(local_storage_entries) == 1
                        and str((local_storage_entries[0] or {}).get("key") or "") == "yis_pc_logindata"
                        and not session_storage_entries
                        and vm_inject_snapshot.get("databaseTableName") == ""
                        and "localStorage/sessionStorage/window 当前只见登录态与通用字段，salesReturnDetailReport.vm 的 databaseTableName 仍为空" not in entry["blocking_issues"]
                    ):
                        entry["blocking_issues"].append(
                            "localStorage/sessionStorage/window 当前只见登录态与通用字段，salesReturnDetailReport.vm 的 databaseTableName 仍为空"
                        )
                    injection_context_after = (
                        ((return_detail_ui_probe.get("baseline") or {}).get("component_injection_context_after_query")) or {}
                    )
                    parent_fields_snapshot = (
                        (injection_context_after.get("parent_fields_snapshot") or {})
                        if isinstance(injection_context_after, dict)
                        else {}
                    )
                    root_data_fields_snapshot = (
                        (injection_context_after.get("root_data_fields_snapshot") or {})
                        if isinstance(injection_context_after, dict)
                        else {}
                    )
                    if (
                        parent_fields_snapshot.get("menuItemId", {}).get("type") == "object"
                        and not root_data_fields_snapshot
                        and "route/parent 注入上下文当前只有 menuItemId/reportLists 等壳层信息，未见额外退货查询参数" not in entry["blocking_issues"]
                    ):
                        entry["blocking_issues"].append(
                            "route/parent 注入上下文当前只有 menuItemId/reportLists 等壳层信息，未见额外退货查询参数"
                        )
            else:
                entry["blocking_issues"] = [
                    "当前默认参数会触发服务端 SQL 截断错误",
                    "尚未完成 type 合法值集合确认",
                    "尚未确认页面附加参数是否影响服务端查询",
                ]
                entry["next_action"] = "先补全 ReturnStockBaseInfo 派生维度与隐藏上下文，再判断是页面遗漏参数还是服务端 SQL 本身失效"
        elif route["title"] == "收货确认":
            if receipt_confirmation_evidence is not None and receipt_confirmation_evidence_path is not None:
                detail = receipt_confirmation_evidence.get("receipt_confirmation") or {}
                entry["stage"] = "已HTTP回证"
                capture_admission_ready = bool(detail.get("capture_admission_ready"))
                entry["trust_level"] = "中" if capture_admission_ready else "低"
                entry["reliability_status"] = "中等可信" if capture_admission_ready else "能跑但不能信"
                entry["blocking_issues"] = list(detail.get("blocking_issues") or [])
                entry["next_action"] = str(
                    (receipt_confirmation_evidence.get("conclusion") or {}).get("next_focus") or entry["next_action"]
                )
                entry["current_judgment"] = str(detail.get("judgment") or entry["current_judgment"])
                entry["analysis_sources"] = list(
                    dict.fromkeys([*entry["analysis_sources"], _repo_path(receipt_confirmation_evidence_path, repo_root)])
                )
                entry["capture_parameter_plan"] = dict(detail.get("capture_parameter_plan") or {})
                entry["secondary_route_blocking_issues"] = list(detail.get("secondary_route_blocking_issues") or [])
                entry["capture_admission_ready"] = capture_admission_ready
                entry["mainline_ready"] = capture_admission_ready
                if receipt_confirmation_ui_probe is not None and receipt_confirmation_ui_probe_path is not None:
                    entry["analysis_sources"] = list(
                        dict.fromkeys([*entry["analysis_sources"], _repo_path(receipt_confirmation_ui_probe_path, repo_root)])
                    )
                    baseline_local = ((receipt_confirmation_ui_probe.get("baseline") or {}).get("local_state_after_query")) or {}
                    baseline_snapshot = (baseline_local or {}).get("snapshot") or {}
                    baseline_ancestry = (receipt_confirmation_ui_probe.get("baseline") or {}).get("component_ancestry_after_query") or []
                    baseline_ancestry_ref_states = (
                        (receipt_confirmation_ui_probe.get("baseline") or {}).get("component_ancestry_ref_states_after_query")
                        or []
                    )
                    order_data_length = int((((baseline_snapshot.get("orderData") or {}).get("length")) or 0))
                    order_detail_length = int((((baseline_snapshot.get("orderDetailData") or {}).get("length")) or 0))
                    select_item_length = int((((baseline_snapshot.get("selectItem") or {}).get("length")) or 0))
                    total_rows = int((baseline_snapshot.get("total") or 0))
                    nested_table_length = int((baseline_local or {}).get("nested_table_length") or 0)
                    secondary_blockers = entry["secondary_route_blocking_issues"]
                    if (
                        total_rows > 0
                        and order_data_length == 0
                        and order_detail_length == 0
                        and select_item_length == 0
                        and nested_table_length == 0
                        and "receiveConfirm 组件已出现 total/page/pageSize，但 orderData/orderDetailData/selectItem 与嵌套表格持续为空" not in secondary_blockers
                    ):
                        secondary_blockers.append(
                            "receiveConfirm 组件已出现 total/page/pageSize，但 orderData/orderDetailData/selectItem 与嵌套表格持续为空"
                        )
                    if baseline_ancestry:
                        receive_confirm_node = next(
                            (
                                item
                                for item in baseline_ancestry
                                if int(item.get("depth") or 0) == 0
                            ),
                            None,
                        )
                        shell_ancestor = next(
                            (
                                item
                                for item in baseline_ancestry
                                if int(item.get("depth") or 0) == 1
                            ),
                            None,
                        )
                        receive_props = (receive_confirm_node or {}).get("props_data_snapshot") or {}
                        receive_nested = (receive_confirm_node or {}).get("nested_snapshots") or {}
                        shell_snapshot = (shell_ancestor or {}).get("snapshot") or {}
                        shell_nested = (shell_ancestor or {}).get("nested_snapshots") or {}
                        shell_collections = (shell_ancestor or {}).get("non_empty_collections") or []
                        shell_collection_fields = {str(item.get("field") or "") for item in shell_collections}
                        if (
                            (shell_snapshot.get("menuItemId") or {}).get("keys") == ["CheckDoc"]
                            and not any(
                                field
                                for field in shell_collection_fields
                                if any(token in field.lower() for token in ("order", "detail", "doc", "row", "item"))
                            )
                            and "receiveConfirm 父链上一层目前只见 menuItemId.CheckDoc 与壳层 tab/menu 集合，未见任何上游订单行缓存" not in secondary_blockers
                        ):
                            secondary_blockers.append(
                                "receiveConfirm 父链上一层目前只见 menuItemId.CheckDoc 与壳层 tab/menu 集合，未见任何上游订单行缓存"
                            )
                        if (
                            str(receive_props.get("menuId") or "") == str((shell_nested.get("menuItemId") or {}).get("CheckDoc") or "")
                            and str(receive_props.get("menuId") or "")
                            and ((receive_nested.get("detailData") or {}).get("currentItem") is None)
                            and "receiveConfirm.menuId 与父链 menuItemId.CheckDoc 当前同值，但 detailData.currentItem 仍为空，说明列表上下文并未继续注入到详情层" not in secondary_blockers
                        ):
                            secondary_blockers.append(
                                "receiveConfirm.menuId 与父链 menuItemId.CheckDoc 当前同值，但 detailData.currentItem 仍为空，说明列表上下文并未继续注入到详情层"
                            )
                    component_method_probes = receipt_confirmation_ui_probe.get("component_method_probes") or []
                    get_data_list_probe = next(
                        (item for item in component_method_probes if item.get("key") == "component_method_getDataList"),
                        None,
                    )
                    if get_data_list_probe is not None:
                        request_endpoints = [
                            str(item.get("endpoint") or "")
                            for item in get_data_list_probe.get("request_diffs") or []
                            if item.get("endpoint")
                        ]
                        local_after = (get_data_list_probe.get("local_state_after") or {}).get("snapshot") or {}
                        if (
                            "SelDocConfirmList" in request_endpoints
                            and int((((local_after.get("orderData") or {}).get("length")) or 0)) == 0
                            and int((((local_after.get("orderDetailData") or {}).get("length")) or 0)) == 0
                            and "getDataList 只会重发 SelDocConfirmList，仍未填充 orderData/orderDetailData" not in secondary_blockers
                        ):
                            secondary_blockers.append(
                                "getDataList 只会重发 SelDocConfirmList，仍未填充 orderData/orderDetailData"
                            )
                    selection_probes = [
                        item
                        for item in component_method_probes
                        if item.get("key") in {"component_method_tableSelectClick", "component_method_selectionChange"}
                    ]
                    if selection_probes:
                        selection_bound = False
                        for probe in selection_probes:
                            local_after = (probe.get("local_state_after") or {}).get("snapshot") or {}
                            nested_after = probe.get("nested_row_context_after") or {}
                            if (
                                int((((local_after.get("selectItem") or {}).get("length")) or 0)) > 0
                                or int((nested_after.get("table_length") or 0)) > 0
                            ):
                                selection_bound = True
                                break
                        if (
                            not selection_bound
                            and "tableSelectClick/selectionChange 当前不会建立稳定选中态，也未填充 selectItem/currentRow" not in secondary_blockers
                        ):
                            secondary_blockers.append(
                                "tableSelectClick/selectionChange 当前不会建立稳定选中态，也未填充 selectItem/currentRow"
                            )
                    ref_method_probes = receipt_confirmation_ui_probe.get("ref_method_probes") or []
                    if ref_method_probes:
                        ref_methods_still_idle = True
                        report_table_page_visible = False
                        header_refresh_without_rows = False
                        for probe in ref_method_probes:
                            if (probe.get("request_diffs") or []):
                                ref_methods_still_idle = False
                            if probe.get("key") == "ref_method_reportTableItem_mainRef_RTM_GetViewGridHead":
                                request_endpoints = [
                                    str(item.get("endpoint") or "")
                                    for item in probe.get("request_diffs") or []
                                    if item.get("endpoint")
                                ]
                                local_after = (probe.get("local_state_after") or {}).get("snapshot") or {}
                                if (
                                    "GetViewGridList" in request_endpoints
                                    and int((((local_after.get("orderData") or {}).get("length")) or 0)) == 0
                                ):
                                    header_refresh_without_rows = True
                            local_after = (probe.get("local_state_after") or {}).get("snapshot") or {}
                            if (
                                int((((local_after.get("orderData") or {}).get("length")) or 0)) > 0
                                or int((((local_after.get("selectItem") or {}).get("length")) or 0)) > 0
                            ):
                                ref_methods_still_idle = False
                            child_refs = (probe.get("ref_state_after") or {}).get("child_refs") or {}
                            report_table_ref = child_refs.get("RTM_reportTable") or {}
                            report_table_snapshot = report_table_ref.get("snapshot") or {}
                            if "tablePage" in report_table_snapshot:
                                report_table_page_visible = True
                        if (
                            ref_methods_still_idle
                            and "reportTableItem_mainRef.RTM_searchConditions/RTM_toggleCheckboxRow 已可调用，但不发请求且仍不填充 orderData/selectItem" not in secondary_blockers
                        ):
                            secondary_blockers.append(
                                "reportTableItem_mainRef.RTM_searchConditions/RTM_toggleCheckboxRow 已可调用，但不发请求且仍不填充 orderData/selectItem"
                            )
                        if (
                            report_table_page_visible
                            and nested_table_length == 0
                            and "reportTableItem_mainRef.$refs.RTM_reportTable 已暴露 tablePage，但仍没有任何行数据" not in secondary_blockers
                        ):
                            secondary_blockers.append(
                                "reportTableItem_mainRef.$refs.RTM_reportTable 已暴露 tablePage，但仍没有任何行数据"
                            )
                        if (
                            header_refresh_without_rows
                            and "reportTableItem_mainRef.RTM_GetViewGridHead 只会重发 GetViewGridList，说明表头链存在但行数据链仍未建立" not in secondary_blockers
                        ):
                            secondary_blockers.append(
                                "reportTableItem_mainRef.RTM_GetViewGridHead 只会重发 GetViewGridList，说明表头链存在但行数据链仍未建立"
                            )
                    child_ref_method_probes = receipt_confirmation_ui_probe.get("child_ref_method_probes") or []
                    child_ref_method_sources = receipt_confirmation_ui_probe.get("child_ref_method_sources") or []
                    ref_method_sources = receipt_confirmation_ui_probe.get("ref_method_sources") or []
                    if child_ref_method_probes:
                        child_methods_still_idle = True
                        local_rebuild_without_data = False
                        table_shape_built_without_rows = False
                        report_table_props_missing_dataset = False
                        report_table_database_is_metadata_only = False
                        report_table_indexeddb_store_missing = False
                        for probe in child_ref_method_probes:
                            if (probe.get("request_diffs") or []):
                                child_methods_still_idle = False
                            local_after = (probe.get("local_state_after") or {}).get("snapshot") or {}
                            if (
                                int((((local_after.get("orderData") or {}).get("length")) or 0)) > 0
                                or int((((local_after.get("selectItem") or {}).get("length")) or 0)) > 0
                            ):
                                child_methods_still_idle = False
                            child_snapshot = (probe.get("child_ref_state_after") or {}).get("snapshot") or {}
                            child_special_snapshot = (probe.get("child_ref_state_after") or {}).get("special_snapshot") or {}
                            if (
                                int((((child_snapshot.get("tableData") or {}).get("length")) or 0)) > 0
                                or int((((child_snapshot.get("data") or {}).get("length")) or 0)) > 0
                            ):
                                child_methods_still_idle = False
                            table_column_len = int((((child_snapshot.get("tableColumn") or {}).get("length")) or 0))
                            all_table_data_len = int((((child_snapshot.get("allTableData") or {}).get("length")) or 0))
                            vxe_table_keys = set(((child_snapshot.get("vxeTable") or {}).get("keys")) or [])
                            if table_column_len > 0 and all_table_data_len == 0 and "tableData" in vxe_table_keys:
                                table_shape_built_without_rows = True
                            props_keys = set(child_special_snapshot.get("props_keys") or [])
                            props_data_keys = set(child_special_snapshot.get("props_data_keys") or [])
                            special_table_data_len = int((((child_special_snapshot.get("tableData") or {}).get("length")) or 0))
                            special_all_table_data_len = int((((child_special_snapshot.get("allTableData") or {}).get("length")) or 0))
                            if (
                                "tableData" in props_keys
                                and "tableData" not in props_data_keys
                                and special_table_data_len == 0
                                and special_all_table_data_len == 0
                            ):
                                report_table_props_missing_dataset = True
                            vxe_special = child_special_snapshot.get("vxeTable_snapshot") or {}
                            database_keys = set(((vxe_special.get("database") or {}).get("keys")) or [])
                            vxe_table_data_len = int((((vxe_special.get("tableData") or {}).get("length")) or 0))
                            vxe_view_data_len = int((((vxe_special.get("viewData") or {}).get("length")) or 0))
                            vxe_init_header_len = int((((vxe_special.get("initHeaderData") or {}).get("length")) or 0))
                            if (
                                {"dbId", "DateBaseName", "Version", "Description", "DataBaseSize", "browser"}.issubset(database_keys)
                                and vxe_table_data_len == 0
                                and vxe_view_data_len == 0
                                and vxe_init_header_len == 0
                            ):
                                report_table_database_is_metadata_only = True
                            indexeddb_after = probe.get("child_ref_indexeddb_after") or {}
                            target_db = indexeddb_after.get("target_database") or {}
                            object_store_names = set(target_db.get("object_store_names") or [])
                            target_store = target_db.get("target_store")
                            database_name = str(indexeddb_after.get("database_name") or "")
                            table_name = str(indexeddb_after.get("database_table_name") or "")
                            if (
                                database_name == "FXDATABASE"
                                and table_name == "receiveConfirm_E003001001_1"
                                and not object_store_names
                                and target_store is None
                            ):
                                report_table_indexeddb_store_missing = True
                            if probe.get("key") in {
                                "child_ref_method_reportTableItem_mainRef_RTM_reportTable_tableDataInit",
                                "child_ref_method_reportTableItem_mainRef_RTM_reportTable_finishViewData",
                            }:
                                if bool(child_snapshot.get("loading")) and all_table_data_len == 0:
                                    local_rebuild_without_data = True
                        if (
                            child_methods_still_idle
                            and "RTM_reportTable.searchConditions/searchDataInfo/pageCondition/GetTotalData/allPageSelect 已可调用，但仍完全 no-op" not in secondary_blockers
                        ):
                            secondary_blockers.append(
                                "RTM_reportTable.searchConditions/searchDataInfo/pageCondition/GetTotalData/allPageSelect 已可调用，但仍完全 no-op"
                            )
                        if (
                            table_shape_built_without_rows
                            and "RTM_reportTable 已暴露 tableColumn，但 allTableData/vxeTable.tableData 仍为空，说明子表结构已建而源数据数组仍未注入" not in secondary_blockers
                        ):
                            secondary_blockers.append(
                                "RTM_reportTable 已暴露 tableColumn，但 allTableData/vxeTable.tableData 仍为空，说明子表结构已建而源数据数组仍未注入"
                            )
                        if (
                            local_rebuild_without_data
                            and "RTM_reportTable.tableDataInit/finishViewData 可调用且会切 loading，但仍未生成任何 tableData/allTableData" not in secondary_blockers
                        ):
                            secondary_blockers.append(
                                "RTM_reportTable.tableDataInit/finishViewData 可调用且会切 loading，但仍未生成任何 tableData/allTableData"
                            )
                        if (
                            report_table_props_missing_dataset
                            and "RTM_reportTable 已声明 tableData 等输入能力，但 propsData 当前只传 databaseTableName/showFooter 等视图参数，未传任何数据集" not in secondary_blockers
                        ):
                            secondary_blockers.append(
                                "RTM_reportTable 已声明 tableData 等输入能力，但 propsData 当前只传 databaseTableName/showFooter 等视图参数，未传任何数据集"
                            )
                        if (
                            report_table_database_is_metadata_only
                            and "RTM_reportTable.vxeTable.database 当前只见本地库元信息，tableData/viewData/initHeaderData 仍全空，说明缺的是更早的源数据注入" not in secondary_blockers
                        ):
                            secondary_blockers.append(
                                "RTM_reportTable.vxeTable.database 当前只见本地库元信息，tableData/viewData/initHeaderData 仍全空，说明缺的是更早的源数据注入"
                            )
                    if (
                        report_table_indexeddb_store_missing
                        and "RTM_reportTable.vxeTable.database 已指向 FXDATABASE，但浏览器实际打开后 object_store_names 为空，receiveConfirm_E003001001_1 并未落成本地表" not in secondary_blockers
                    ):
                        secondary_blockers.append(
                            "RTM_reportTable.vxeTable.database 已指向 FXDATABASE，但浏览器实际打开后 object_store_names 为空，receiveConfirm_E003001001_1 并未落成本地表"
                        )
                    baseline_payload = receipt_confirmation_ui_probe.get("baseline") or {}
                    baseline_store_state = baseline_payload.get("component_store_after_query") or {}
                    baseline_global_storage = baseline_payload.get("component_global_storage_after_query") or {}
                    store_state_snapshot = baseline_store_state.get("store_state_snapshot") or {}
                    root_data_snapshot = baseline_store_state.get("root_data_snapshot") or {}
                    ancestry_method_sources = baseline_payload.get("component_ancestry_method_sources_after_query") or []
                    if (
                        isinstance(store_state_snapshot, dict)
                        and set(store_state_snapshot.keys()) == {"cleardata"}
                        and "receiveConfirm.$store.state 当前只见 cleardata 标志，未见任何订单/详情缓存" not in secondary_blockers
                    ):
                        secondary_blockers.append(
                            "receiveConfirm.$store.state 当前只见 cleardata 标志，未见任何订单/详情缓存"
                        )
                    if (
                        isinstance(root_data_snapshot, dict)
                        and not root_data_snapshot
                        and "receiveConfirm.$root._data 当前未见任何订单/详情缓存字段" not in secondary_blockers
                    ):
                        secondary_blockers.append(
                            "receiveConfirm.$root._data 当前未见任何订单/详情缓存字段"
                        )
                    local_storage_entries = baseline_global_storage.get("local_storage_entries") or []
                    session_storage_entries = baseline_global_storage.get("session_storage_entries") or []
                    window_snapshot = baseline_global_storage.get("window_snapshot") or {}
                    vm_inject_snapshot = baseline_global_storage.get("vm_inject_snapshot") or {}
                    injection_context = baseline_payload.get("component_injection_context_after_query") or {}
                    detail_data_snapshot = injection_context.get("detail_data_snapshot") or {}
                    detail_pager_snapshot = detail_data_snapshot.get("pager") or {}
                    shell_context = injection_context.get("shell_context") or {}
                    editable_tabs = shell_context.get("editableTabs") or {}
                    editable_tab_rows = editable_tabs.get("sample_rows") or []
                    root_event_hub = injection_context.get("root_event_hub") or {}
                    order_data_in_vm = int((((vm_inject_snapshot.get("orderData") or {}).get("length")) or 0))
                    order_detail_in_vm = int((((vm_inject_snapshot.get("orderDetailData") or {}).get("length")) or 0))
                    order_hj_in_vm = int((((vm_inject_snapshot.get("orderHJData") or {}).get("length")) or 0))
                    order_detail_hj_in_vm = int((((vm_inject_snapshot.get("orderDetailHJData") or {}).get("length")) or 0))
                    select_item_in_vm = int((((vm_inject_snapshot.get("selectItem") or {}).get("length")) or 0))
                    check_list_in_vm = int((((vm_inject_snapshot.get("CheckList") or {}).get("length")) or 0))
                    detail_data_in_vm = vm_inject_snapshot.get("detailData") or {}
                    if (
                        vm_inject_snapshot
                        and order_data_in_vm == 0
                        and order_detail_in_vm == 0
                        and order_hj_in_vm == 0
                        and order_detail_hj_in_vm == 0
                        and select_item_in_vm == 0
                        and check_list_in_vm == 0
                        and isinstance(detail_data_in_vm, dict)
                        and detail_data_in_vm.get("type") == "object"
                        and "receiveConfirm vm 注入字段已存在，但 orderData/orderDetailData/orderHJData/selectItem/CheckList 仍全为空，detailData 也还只是壳对象" not in secondary_blockers
                    ):
                        secondary_blockers.append(
                            "receiveConfirm vm 注入字段已存在，但 orderData/orderDetailData/orderHJData/selectItem/CheckList 仍全为空，detailData 也还只是壳对象"
                        )
                    if (
                        total_rows > 0
                        and int(detail_pager_snapshot.get("total") or 0) == 0
                        and "receiveConfirm 根层 total=300，但 detailData.pager.total 仍为 0，说明详情层分页上下文尚未承接主列表数据" not in secondary_blockers
                    ):
                        secondary_blockers.append(
                            "receiveConfirm 根层 total=300，但 detailData.pager.total 仍为 0，说明详情层分页上下文尚未承接主列表数据"
                        )
                    if (
                        editable_tab_rows
                        and all(set((row or {}).keys()) <= {"FuncUrl", "FuncName"} for row in editable_tab_rows if isinstance(row, dict))
                        and "父链 editableTabs 当前只保留 FuncUrl/FuncName 壳层 tab 元信息，未见任何附加数据载荷" not in secondary_blockers
                    ):
                        secondary_blockers.append(
                            "父链 editableTabs 当前只保留 FuncUrl/FuncName 壳层 tab 元信息，未见任何附加数据载荷"
                        )
                    if (
                        isinstance(root_event_hub, dict)
                        and root_event_hub.get("keys")
                        and not (root_event_hub.get("event_keys") or [])
                        and "根层 yisEventHub 已存在但 _events 为空，未见通过事件总线注入明细数据的迹象" not in secondary_blockers
                    ):
                        secondary_blockers.append(
                            "根层 yisEventHub 已存在但 _events 为空，未见通过事件总线注入明细数据的迹象"
                        )
                    if (
                        not local_storage_entries
                        and not session_storage_entries
                        and not window_snapshot
                        and not vm_inject_snapshot
                        and "receiveConfirm 对应的 localStorage/sessionStorage/window/vm 注入快照当前也未见任何订单/详情缓存线索" not in secondary_blockers
                    ):
                        secondary_blockers.append(
                            "receiveConfirm 对应的 localStorage/sessionStorage/window/vm 注入快照当前也未见任何订单/详情缓存线索"
                        )
                    component_methods_native_wrapped = False
                    component_method_sources = baseline_payload.get("component_method_sources") or {}
                    component_methods = component_method_sources.get("methods") or {}
                    if component_methods and all(
                        "[native code]" in str((meta or {}).get("preview") or "")
                        for meta in component_methods.values()
                    ):
                        component_methods_native_wrapped = True
                    ref_methods_native_wrapped = False
                    for block in ref_method_sources:
                        methods = block.get("methods") or {}
                        if methods and all("[native code]" in str((meta or {}).get("preview") or "") for meta in methods.values()):
                            ref_methods_native_wrapped = True
                    child_methods_native_wrapped = False
                    for block in child_ref_method_sources:
                        methods = block.get("methods") or {}
                        if methods and all("[native code]" in str((meta or {}).get("preview") or "") for meta in methods.values()):
                            child_methods_native_wrapped = True
                    if (
                        component_methods_native_wrapped
                        and "receiveConfirm.getDataList/checkDetail/getDetailData/LogisticInfoClick 等关键方法源码当前都只暴露 native code 包装，已无法继续从根组件函数体反推注入链" not in secondary_blockers
                    ):
                        secondary_blockers.append(
                            "receiveConfirm.getDataList/checkDetail/getDetailData/LogisticInfoClick 等关键方法源码当前都只暴露 native code 包装，已无法继续从根组件函数体反推注入链"
                        )
                    ancestry_depth_0 = next(
                        (item for item in ancestry_method_sources if int(item.get("depth") or 0) == 0),
                        None,
                    )
                    ancestry_depth_1 = next(
                        (item for item in ancestry_method_sources if int(item.get("depth") or 0) == 1),
                        None,
                    )
                    depth_1_methods = (ancestry_depth_1 or {}).get("methods") or []
                    if (
                        depth_1_methods
                        and all("[native code]" in str((item or {}).get("preview") or "") for item in depth_1_methods)
                        and "receiveConfirm 父链壳层方法当前也只暴露 native code 包装，说明更早的菜单/页面注入链同样不可从函数体继续回溯" not in secondary_blockers
                    ):
                        secondary_blockers.append(
                            "receiveConfirm 父链壳层方法当前也只暴露 native code 包装，说明更早的菜单/页面注入链同样不可从函数体继续回溯"
                        )
                    if (
                        ref_methods_native_wrapped
                        and child_methods_native_wrapped
                        and "reportTableItem_mainRef 与 RTM_reportTable 的关键方法源码当前都只暴露 native code 包装，已无法继续从函数体反推初始化链" not in secondary_blockers
                    ):
                        secondary_blockers.append(
                            "reportTableItem_mainRef 与 RTM_reportTable 的关键方法源码当前都只暴露 native code 包装，已无法继续从函数体反推初始化链"
                        )
                    invoice_shell_ref = next(
                        (
                            item
                            for item in baseline_ancestry_ref_states
                            if str(item.get("ref_name") or "") == "invoice01"
                        ),
                        None,
                    )
                    navmenu_shell_ref = next(
                        (
                            item
                            for item in baseline_ancestry_ref_states
                            if str(item.get("ref_name") or "") == "navmenu"
                        ),
                        None,
                    )
                    if (
                        invoice_shell_ref
                        and navmenu_shell_ref
                        and str(invoice_shell_ref.get("component_name") or "") == "receiveConfirm"
                        and not (navmenu_shell_ref.get("matched_keys") or [])
                        and not (navmenu_shell_ref.get("props_data_keys") or [])
                        and "父链 refs 中 invoice01 当前只是回指同一个 receiveConfirm 实例，navmenu 也未见任何附加数据载荷，说明壳层 ref 仍不是缺失数据的来源" not in secondary_blockers
                    ):
                        secondary_blockers.append(
                            "父链 refs 中 invoice01 当前只是回指同一个 receiveConfirm 实例，navmenu 也未见任何附加数据载荷，说明壳层 ref 仍不是缺失数据的来源"
                        )
                    entry["next_action"] = (
                        "收货确认主列表已 admit；下一步应沿 receiveConfirm.menuId、父链 menuItemId.CheckDoc 与 "
                        "detailData.currentItem 的断点继续回溯更早的上游数据注入点，并追 RTM_reportTable."
                        "props.tableData、allTableData/vxeTable.tableData、vxeTable.database 与 FXDATABASE/"
                        "receiveConfirm_E003001001_1 本地表初始化的来源，"
                        "确认为何 receiveConfirm / reportTableItem_mainRef / RTM_reportTable 三层都有分页状态却始终没有行数据。"
                    )
            else:
                entry["blocking_issues"] = [
                    "尚未确认真实主接口是否稳定",
                    "尚未完成 page/time/search 的 HTTP 回证",
                    "尚未确认详情/确认动作是否依赖隐藏页面上下文",
                ]
                entry["next_action"] = "先确认 SelDocConfirmList 的主列表行为，再补页面动作链与 HTTP 回证"
        elif route["title"] == "门店盘点单":
            if store_stocktaking_evidence is not None and store_stocktaking_evidence_path is not None:
                detail = store_stocktaking_evidence.get("store_stocktaking") or {}
                entry["stage"] = "已HTTP回证"
                capture_admission_ready = bool(detail.get("capture_admission_ready"))
                entry["trust_level"] = "中" if capture_admission_ready else "低"
                entry["reliability_status"] = "中等可信" if capture_admission_ready else "能跑但不能信"
                entry["blocking_issues"] = list(detail.get("blocking_issues") or [])
                entry["next_action"] = str(
                    (store_stocktaking_evidence.get("conclusion") or {}).get("next_focus") or entry["next_action"]
                )
                entry["current_judgment"] = str(detail.get("judgment") or entry["current_judgment"])
                entry["analysis_sources"] = list(
                    dict.fromkeys([*entry["analysis_sources"], _repo_path(store_stocktaking_evidence_path, repo_root)])
                )
                entry["capture_parameter_plan"] = dict(detail.get("capture_parameter_plan") or {})
                entry["secondary_route_blocking_issues"] = list(detail.get("secondary_route_blocking_issues") or [])
                entry["capture_admission_ready"] = capture_admission_ready
                entry["mainline_ready"] = capture_admission_ready
                if store_stocktaking_ui_probe is not None and store_stocktaking_ui_probe_path is not None:
                    entry["analysis_sources"] = list(
                        dict.fromkeys([*entry["analysis_sources"], _repo_path(store_stocktaking_ui_probe_path, repo_root)])
                    )
                    diff_probe = next(
                        (
                            item
                            for item in store_stocktaking_ui_probe.get("component_method_probes") or []
                            if item.get("key") == "component_method_getDiffData"
                        ),
                        None,
                    )
                    detail_probe = next(
                        (
                            item
                            for item in store_stocktaking_ui_probe.get("component_method_probes") or []
                            if item.get("key") == "component_method_getDetailList"
                        ),
                        None,
                    )
                    diff_rows = int(
                        ((((diff_probe or {}).get("local_state_after") or {}).get("snapshot") or {}).get("orderDiffData") or {}).get("length")
                        or 0
                    )
                    diff_summary_rows = int(
                        ((((diff_probe or {}).get("local_state_after") or {}).get("snapshot") or {}).get("orderDiffHJData") or {}).get("length")
                        or 0
                    )
                    detail_rows = int(
                        ((((detail_probe or {}).get("local_state_after") or {}).get("snapshot") or {}).get("orderDetailData") or {}).get("length")
                        or 0
                    )
                    show_diff_page = bool(
                        ((((diff_probe or {}).get("local_state_after") or {}).get("snapshot") or {}).get("showDiffPage"))
                    )
                    show_detail_page = bool(
                        ((((detail_probe or {}).get("local_state_after") or {}).get("snapshot") or {}).get("showDetailPage"))
                    )
                    entry["observed_local_secondary_state"] = {
                        "order_diff_rows": diff_rows,
                        "order_diff_summary_rows": diff_summary_rows,
                        "order_detail_rows": detail_rows,
                        "show_diff_page": show_diff_page,
                        "show_detail_page": show_detail_page,
                    }
                    if diff_rows > 0:
                        secondary_issues = list(entry.get("secondary_route_blocking_issues") or [])
                        secondary_issues = [
                            issue
                            for issue in secondary_issues
                            if issue != "统计损溢二级接口仍待识别"
                        ]
                        if "统计损溢已能本地填充 orderDiffData，但尚未确认是独立 HTTP route 还是本地派生数据" not in secondary_issues:
                            secondary_issues.append("统计损溢已能本地填充 orderDiffData，但尚未确认是独立 HTTP route 还是本地派生数据")
                        entry["secondary_route_blocking_issues"] = secondary_issues
                        entry["next_action"] = (
                            "门店盘点单主列表已可准入 capture；下一步应优先确认 getDiffData(row) 产出的本地损溢数据是否可作为二级 raw route，"
                            "再决定是否继续追独立 HTTP 接口。"
                        )
            else:
                entry["blocking_issues"] = [
                    "尚未确认真实主接口是否稳定",
                    "尚未完成 stat/date 的 HTTP 回证",
                    "尚未确认查看明细/统计损溢/条码记录是否依赖隐藏动作链",
                ]
                entry["next_action"] = "先确认 SelDocManageList 的主列表行为，再补明细/损溢动作链与 HTTP 回证"
        entries.append(entry)

    if has_sales_evidence:
        entries.extend(
            _build_sales_evidence_entries(
                sales_evidence=sales_evidence,
                routes_by_title=routes_by_title,
                page_records=page_records,
                menu_coverage_index=menu_coverage_index,
                repo_root=repo_root,
                sales_evidence_path=sales_evidence_path,
            )
        )
    if inventory_admission is not None and inventory_evidence_path is not None and inventory_evidence is not None:
        entries.extend(
            _build_inventory_evidence_entries(
                inventory_evidence=inventory_evidence,
                inventory_admission=inventory_admission,
                inventory_outin_research_path=inventory_outin_research_path,
                routes_by_title=routes_by_title,
                page_records=page_records,
                menu_coverage_index=menu_coverage_index,
                repo_root=repo_root,
                inventory_evidence_path=inventory_evidence_path,
            )
        )
    if member_evidence is not None and member_evidence_path is not None:
        entries.extend(
            _build_member_evidence_entries(
                member_evidence=member_evidence,
                routes_by_title=routes_by_title,
                page_records=page_records,
                menu_coverage_index=menu_coverage_index,
                repo_root=repo_root,
                member_evidence_path=member_evidence_path,
            )
        )
    if member_maintenance_evidence is not None and member_maintenance_evidence_path is not None:
        entries.extend(
            _build_member_maintenance_evidence_entries(
                member_maintenance_evidence=member_maintenance_evidence,
                routes_by_title=routes_by_title,
                page_records=page_records,
                menu_coverage_index=menu_coverage_index,
                repo_root=repo_root,
                member_maintenance_evidence_path=member_maintenance_evidence_path,
            )
        )
    if member_analysis_snapshot_evidence is not None and member_analysis_snapshot_evidence_path is not None:
        entries.extend(
            _build_member_analysis_snapshot_entries(
                member_analysis_snapshot_evidence=member_analysis_snapshot_evidence,
                routes_by_title=routes_by_title,
                page_records=page_records,
                menu_coverage_index=menu_coverage_index,
                repo_root=repo_root,
                member_analysis_snapshot_evidence_path=member_analysis_snapshot_evidence_path,
            )
        )
    if member_sales_rank_snapshot_evidence is not None and member_sales_rank_snapshot_evidence_path is not None:
        entries.extend(
            _build_member_sales_rank_snapshot_entries(
                member_sales_rank_snapshot_evidence=member_sales_rank_snapshot_evidence,
                routes_by_title=routes_by_title,
                page_records=page_records,
                menu_coverage_index=menu_coverage_index,
                repo_root=repo_root,
                member_sales_rank_snapshot_evidence_path=member_sales_rank_snapshot_evidence_path,
            )
        )
    if product_evidence is not None and product_evidence_path is not None:
        entries.extend(
            _build_product_evidence_entries(
                product_evidence=product_evidence,
                routes_by_title=routes_by_title,
                page_records=page_records,
                menu_coverage_index=menu_coverage_index,
                repo_root=repo_root,
                product_evidence_path=product_evidence_path,
            )
        )
    if product_sales_snapshot_evidence is not None and product_sales_snapshot_evidence_path is not None:
        entries.extend(
            _build_product_sales_snapshot_entries(
                product_sales_snapshot_evidence=product_sales_snapshot_evidence,
                routes_by_title=routes_by_title,
                page_records=page_records,
                menu_coverage_index=menu_coverage_index,
                repo_root=repo_root,
                product_sales_snapshot_evidence_path=product_sales_snapshot_evidence_path,
            )
        )
    if daily_payment_snapshot_evidence is not None and daily_payment_snapshot_evidence_path is not None:
        entries.extend(
            _build_daily_payment_snapshot_entries(
                daily_payment_snapshot_evidence=daily_payment_snapshot_evidence,
                routes_by_title=routes_by_title,
                page_records=page_records,
                menu_coverage_index=menu_coverage_index,
                repo_root=repo_root,
                daily_payment_snapshot_evidence_path=daily_payment_snapshot_evidence_path,
            )
        )
    if stored_value_card_summary_snapshot_evidence is not None and stored_value_card_summary_snapshot_evidence_path is not None:
        entries.extend(
            _build_stored_value_card_summary_snapshot_entries(
                stored_value_card_summary_snapshot_evidence=stored_value_card_summary_snapshot_evidence,
                routes_by_title=routes_by_title,
                page_records=page_records,
                menu_coverage_index=menu_coverage_index,
                repo_root=repo_root,
                stored_value_card_summary_snapshot_evidence_path=stored_value_card_summary_snapshot_evidence_path,
            )
        )
    if stored_value_by_store_snapshot_evidence is not None and stored_value_by_store_snapshot_evidence_path is not None:
        entries.extend(
            _build_stored_value_by_store_snapshot_entries(
                stored_value_by_store_snapshot_evidence=stored_value_by_store_snapshot_evidence,
                routes_by_title=routes_by_title,
                page_records=page_records,
                menu_coverage_index=menu_coverage_index,
                repo_root=repo_root,
                stored_value_by_store_snapshot_evidence_path=stored_value_by_store_snapshot_evidence_path,
            )
        )
    if customer_evidence is not None and customer_evidence_path is not None:
        entries.extend(
            _build_customer_evidence_entries(
                customer_evidence=customer_evidence,
                routes_by_title=routes_by_title,
                page_records=page_records,
                menu_coverage_index=menu_coverage_index,
                repo_root=repo_root,
                customer_evidence_path=customer_evidence_path,
            )
        )
    if stored_value_evidence is not None and stored_value_evidence_path is not None:
        entries.extend(
            _build_stored_value_evidence_entries(
                stored_value_evidence=stored_value_evidence,
                routes_by_title=routes_by_title,
                page_records=page_records,
                menu_coverage_index=menu_coverage_index,
                repo_root=repo_root,
                stored_value_evidence_path=stored_value_evidence_path,
            )
        )
    entries.extend(
        _build_store_stocktaking_secondary_entries(
            page_records=page_records,
            menu_coverage_index=menu_coverage_index,
            repo_root=repo_root,
            store_stocktaking_ui_probe_path=store_stocktaking_ui_probe_path,
            store_stocktaking_ui_probe=store_stocktaking_ui_probe,
        )
    )
    entries.extend(
        _build_researched_unknown_page_entries(
            page_records=page_records,
            menu_coverage_index=menu_coverage_index,
            known_titles=known_titles,
        )
    )
    entries.extend(
        _build_unknown_page_entries(
            menu_coverage_payload,
            repo_root=repo_root,
            menu_coverage_path=menu_coverage_path,
            page_records=page_records,
        )
    )
    entries = _with_capture_runtime(entries, capture_runtime_index)

    sources = BoardSourceFiles(
        report_matrix=report_matrix_path,
        page_research_files=page_files,
        sales_evidence=sales_evidence_path,
        inventory_evidence=inventory_evidence_path,
        store_stocktaking_evidence=store_stocktaking_evidence_path,
        store_stocktaking_ui_probe=store_stocktaking_ui_probe_path,
        return_detail_evidence=return_detail_evidence_path,
        return_detail_ui_probe=return_detail_ui_probe_path,
        receipt_confirmation_evidence=receipt_confirmation_evidence_path,
        receipt_confirmation_ui_probe=receipt_confirmation_ui_probe_path,
        member_evidence=member_evidence_path,
        member_maintenance_evidence=member_maintenance_evidence_path,
        member_analysis_snapshot_evidence=member_analysis_snapshot_evidence_path,
        member_sales_rank_snapshot_evidence=member_sales_rank_snapshot_evidence_path,
        product_evidence=product_evidence_path,
        product_sales_snapshot_evidence=product_sales_snapshot_evidence_path,
        daily_payment_snapshot_evidence=daily_payment_snapshot_evidence_path,
        stored_value_card_summary_snapshot_evidence=stored_value_card_summary_snapshot_evidence_path,
        stored_value_by_store_snapshot_evidence=stored_value_by_store_snapshot_evidence_path,
        customer_evidence=customer_evidence_path,
        stored_value_evidence=stored_value_evidence_path,
        inventory_outin_research=inventory_outin_research_path,
        menu_coverage_audit=menu_coverage_path,
        capture_runtime_files=capture_runtime_files,
    )
    return entries, sources


def _domain_summary(entries: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for domain in DOMAIN_ORDER:
        domain_entries = [entry for entry in entries if entry["domain"] == domain]
        stage_counter = Counter(entry["stage"] for entry in domain_entries)
        trust_counter = Counter(entry["trust_level"] for entry in domain_entries)
        summary[domain] = {
            "route_count": len(domain_entries),
            "http_verified": stage_counter.get("已HTTP回证", 0),
            "single_variable": stage_counter.get("已单变量", 0),
            "baseline_only": stage_counter.get("已基线", 0),
            "discovered_only": stage_counter.get("已发现", 0),
            "high_trust": trust_counter.get("高", 0),
            "medium_trust": trust_counter.get("中", 0),
            "low_trust": trust_counter.get("低", 0),
            "research_map_complete": sum(1 for entry in domain_entries if entry["research_map_complete"]),
        }
    return summary


def build_api_maturity_board(repo_root: Path, analysis_root: Path) -> dict[str, Any]:
    entries, sources = _build_route_entries(repo_root=repo_root, analysis_root=analysis_root)
    entries.sort(
        key=lambda item: (
            DOMAIN_ORDER[item["domain"]],
            ROLE_ORDER[item["role"]],
            -STAGE_ORDER[item["stage"]],
            item["route"],
        )
    )
    total_routes = len(entries)
    stage_counter = Counter(entry["stage"] for entry in entries)
    trust_counter = Counter(entry["trust_level"] for entry in entries)
    reliability_counter = Counter(entry["reliability_status"] for entry in entries)
    blocker_counter = Counter()
    for entry in entries:
        for issue in entry["blocking_issues"]:
            blocker_counter[issue] += 1

    menu_coverage_payload = _load_json(sources.menu_coverage_audit) or {}
    menu_coverage_summary = menu_coverage_payload.get("summary") or {}
    risk_map_complete_count = sum(1 for entry in entries if entry["research_map_complete"])
    visible_but_untracked_count = int(menu_coverage_summary.get("visible_but_untracked_count") or 0)
    menu_coverage_audit_complete = bool(
        sources.menu_coverage_audit
        and menu_coverage_summary.get("audit_complete")
        and menu_coverage_summary.get("all_visible_pages_classified")
    )
    global_risk_map_complete = menu_coverage_audit_complete and visible_but_untracked_count == 0
    for entry in entries:
        entry["ingestion_blocked_by_global_gate"] = not global_risk_map_complete

    summary = {
        "total_routes": total_routes,
        "stage_counts": dict(stage_counter),
        "trust_counts": dict(trust_counter),
        "reliability_counts": dict(reliability_counter),
        "http_verified_count": int(stage_counter.get("已HTTP回证", 0)),
        "mainline_ready_count": sum(1 for entry in entries if entry["mainline_ready"]),
        "capture_written_once_count": sum(1 for entry in entries if entry.get("capture_written_once")),
        "research_map_complete_count": risk_map_complete_count,
        "global_risk_map_complete": global_risk_map_complete,
        "menu_coverage_audit_complete": menu_coverage_audit_complete,
        "menu_coverage": {
            "menu_node_count": int(menu_coverage_summary.get("menu_node_count") or 0),
            "container_only_count": int(menu_coverage_summary.get("container_only_count") or 0),
            "clickable_page_count": int(menu_coverage_summary.get("clickable_page_count") or 0),
            "covered_count": int(menu_coverage_summary.get("covered_count") or 0),
            "visible_but_untracked_count": int(menu_coverage_summary.get("visible_but_untracked_count") or 0),
            "visible_but_failed_count": int(menu_coverage_summary.get("visible_but_failed_count") or 0),
            "unmatched_registry_target_count": len(menu_coverage_summary.get("unmatched_registry_targets") or []),
        },
        "top_blockers": [{"issue": issue, "count": count} for issue, count in blocker_counter.most_common(8)],
        "domains": _domain_summary(entries),
    }

    source_files = {
        "report_matrix": _repo_path(sources.report_matrix, repo_root) if sources.report_matrix else None,
        "page_research_files": [_repo_path(path, repo_root) for path in sources.page_research_files],
        "sales_evidence": _repo_path(sources.sales_evidence, repo_root) if sources.sales_evidence else None,
        "inventory_evidence": _repo_path(sources.inventory_evidence, repo_root) if sources.inventory_evidence else None,
        "store_stocktaking_evidence": _repo_path(sources.store_stocktaking_evidence, repo_root)
        if sources.store_stocktaking_evidence
        else None,
        "return_detail_evidence": _repo_path(sources.return_detail_evidence, repo_root) if sources.return_detail_evidence else None,
        "return_detail_ui_probe": _repo_path(sources.return_detail_ui_probe, repo_root)
        if sources.return_detail_ui_probe
        else None,
        "receipt_confirmation_evidence": _repo_path(sources.receipt_confirmation_evidence, repo_root)
        if sources.receipt_confirmation_evidence
        else None,
        "receipt_confirmation_ui_probe": _repo_path(sources.receipt_confirmation_ui_probe, repo_root)
        if sources.receipt_confirmation_ui_probe
        else None,
        "member_evidence": _repo_path(sources.member_evidence, repo_root) if sources.member_evidence else None,
        "member_maintenance_evidence": _repo_path(sources.member_maintenance_evidence, repo_root)
        if sources.member_maintenance_evidence
        else None,
        "member_analysis_snapshot_evidence": _repo_path(sources.member_analysis_snapshot_evidence, repo_root)
        if sources.member_analysis_snapshot_evidence
        else None,
        "member_sales_rank_snapshot_evidence": _repo_path(sources.member_sales_rank_snapshot_evidence, repo_root)
        if sources.member_sales_rank_snapshot_evidence
        else None,
        "product_evidence": _repo_path(sources.product_evidence, repo_root) if sources.product_evidence else None,
        "product_sales_snapshot_evidence": _repo_path(sources.product_sales_snapshot_evidence, repo_root)
        if sources.product_sales_snapshot_evidence
        else None,
        "daily_payment_snapshot_evidence": _repo_path(sources.daily_payment_snapshot_evidence, repo_root)
        if sources.daily_payment_snapshot_evidence
        else None,
        "stored_value_card_summary_snapshot_evidence": _repo_path(sources.stored_value_card_summary_snapshot_evidence, repo_root)
        if sources.stored_value_card_summary_snapshot_evidence
        else None,
        "stored_value_by_store_snapshot_evidence": _repo_path(sources.stored_value_by_store_snapshot_evidence, repo_root)
        if sources.stored_value_by_store_snapshot_evidence
        else None,
        "customer_evidence": _repo_path(sources.customer_evidence, repo_root) if sources.customer_evidence else None,
        "stored_value_evidence": _repo_path(sources.stored_value_evidence, repo_root) if sources.stored_value_evidence else None,
        "inventory_outin_research": _repo_path(sources.inventory_outin_research, repo_root) if sources.inventory_outin_research else None,
        "menu_coverage_audit": _repo_path(sources.menu_coverage_audit, repo_root) if sources.menu_coverage_audit else None,
        "capture_runtime_files": [_repo_path(path, repo_root) for path in sources.capture_runtime_files],
        "ledger_files": [str(relative_path) for _, _, relative_path in LEDGER_SPECS],
    }

    return {
        "summary": summary,
        "source_files": source_files,
        "entries": entries,
        "admission_gate": [
            "当前账号可见全域已经完成菜单覆盖审计；所有可见页面都已分类到 covered / visible_but_untracked / visible_but_failed / container_only",
            "已知读接口路线都至少完成风险地图（基线 + 分页/枚举/范围风险 + 主源/快照分类）",
            "页面研究已确认接口语义",
            "纯 HTTP 可稳定重放",
            "关键参数已分清视图切换或数据范围切换",
            "分页语义已确认",
            "至少有一条对账或证据闭环可解释主要指标",
            "当前没有高优先级 issue_flags",
        ],
    }


def render_api_maturity_board_markdown(board: dict[str, Any]) -> str:
    summary = board["summary"]
    lines = [
        "# ERP API 成熟度总览",
        "",
        "> 本文件由 `scripts/build_erp_api_maturity_board.py` 生成，作为后续推进的唯一状态面板。执行路线图见 [ERP Capture 全量导入路线图](./capture-ingestion-roadmap.md)。",
        "",
        "## 1. 当前目标",
        "",
        "- 在当前合法账号/角色可见范围内，先把所有可读报表与查询数据做成完整风险地图，再按可信度分层纳入主链。",
        "- `capture` 负责原始留痕，`serving` 继续只做可演进投影；在全域风险地图完成前，不新增正式 capture 主链路线。",
        "- 后续推进一律以本总览为入口：先看总览，再看路线图，再看对应 ledger 与 analysis 证据文件。",
        "",
        "## 2. 全域门槛与主链准入标准",
        "",
    ]
    for item in board["admission_gate"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 3. 当前总体状态",
            "",
            f"- 路线总数：`{summary['total_routes']}`",
            f"- 路线级风险地图已完成：`{summary['research_map_complete_count']} / {summary['total_routes']}`",
            f"- 当前账号可见菜单覆盖审计完成：`{'是' if summary['menu_coverage_audit_complete'] else '否'}`",
            f"- 当前账号可点击页面：`{summary['menu_coverage']['clickable_page_count']}`",
            f"- 已覆盖页面：`{summary['menu_coverage']['covered_count']}`",
            f"- visible_but_untracked：`{summary['menu_coverage']['visible_but_untracked_count']}`",
            f"- visible_but_failed：`{summary['menu_coverage']['visible_but_failed_count']}`",
            f"- container_only：`{summary['menu_coverage']['container_only_count']}`",
            f"- 全域门槛已达成：`{'是' if summary['global_risk_map_complete'] else '否'}`",
            f"- 已准入主链：`{summary['mainline_ready_count']}`",
            f"- 已真实写入 capture：`{summary['capture_written_once_count']}`",
            f"- 已 HTTP 回证：`{summary['stage_counts'].get('已HTTP回证', 0)}`",
            f"- 已单变量：`{summary['stage_counts'].get('已单变量', 0)}`",
            f"- 仅基线：`{summary['stage_counts'].get('已基线', 0)}`",
            f"- 仅发现：`{summary['stage_counts'].get('已发现', 0)}`",
            f"- 能跑但不能信：`{summary['reliability_counts'].get('能跑但不能信', 0)}`",
            f"- 中等可信：`{summary['reliability_counts'].get('中等可信', 0)}`",
            f"- 高可信：`{summary['reliability_counts'].get('高可信', 0)}`",
            "",
            "当前高优先级 blocker：",
        ]
    )
    for blocker in summary["top_blockers"]:
        lines.append(f"- `{blocker['count']}` 次：{blocker['issue']}")

    lines.extend(
        [
            "",
            "## 4. 分域状态",
            "",
            "| 域 | 路线数 | 风险地图完成 | 已HTTP回证 | 已单变量 | 仅基线 | 仅发现 | 中高可信 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for domain_key, domain_label, _ in LEDGER_SPECS:
        domain_summary = summary["domains"][domain_key]
        medium_high = domain_summary["high_trust"] + domain_summary["medium_trust"]
        lines.append(
            f"| {domain_label} | {domain_summary['route_count']} | {domain_summary['research_map_complete']} | {domain_summary['http_verified']} | "
            f"{domain_summary['single_variable']} | {domain_summary['baseline_only']} | "
            f"{domain_summary['discovered_only']} | {medium_high} |"
        )

    lines.extend(["", "## 5. 路线状态板", ""])
    for domain_key, domain_label, _ in LEDGER_SPECS:
        lines.append(f"### {domain_label}")
        lines.append("")
        lines.append("| 路线 | 来源分类 | 阶段 | 风险地图完成 | 覆盖状态 | 可信度 | 全域门槛阻塞 | 主链就绪 | 已写capture | 最新batch | 菜单路径 | 剩余问题 | 下一步 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for entry in board["entries"]:
            if entry["domain"] != domain_key:
                continue
            blockers = "；".join(entry["blocking_issues"]) if entry["blocking_issues"] else "-"
            menu_path = " / ".join(entry.get("menu_path") or []) or "-"
            latest_batch = entry.get("latest_capture_batch_id") or "-"
            lines.append(
                f"| {entry['route']} | {entry['source_kind']} | {entry['stage']} | "
                f"{'是' if entry['research_map_complete'] else '否'} | {entry.get('coverage_status', '-')} | {entry['reliability_status']} | "
                f"{'是' if entry['ingestion_blocked_by_global_gate'] else '否'} | "
                f"{'是' if entry['mainline_ready'] else '否'} | {'是' if entry.get('capture_written_once') else '否'} | "
                f"`{latest_batch}` | {menu_path} | {blockers} | {entry['next_action']} |"
            )
        lines.append("")

    lines.extend(["## 6. 当前推进顺序", ""])
    lines.extend(
        [
            "1. 当前账号可见全域风险地图已经完成，下一步先执行销售首批 capture 准入。",
            "2. 销售域正常路线按 `sales_documents_head` / `sales_document_lines` 进入 capture，`sales_reverse_document_lines` 只保留研究留痕。",
            "3. 在 serving 继续冻结的前提下，先观测销售批次回归指标与异常阈值表现。",
            "4. 再收口库存域的 `type`、`doctype` 与 `stockflag=1/2`。",
            "5. 最后才轮到会员 / 储值 / 流水单据的 HTTP 回证与主链准入评估。",
            "",
            "## 7. 证据来源",
            "",
        ]
    )
    for label, value in board["source_files"].items():
        if isinstance(value, list):
            lines.append(f"- `{label}`")
            for item in value:
                lines.append(f"  - `{item}`")
        elif value:
            lines.append(f"- `{label}`: `{value}`")
    lines.append("")
    return "\n".join(lines)
