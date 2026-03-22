from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.inventory_capture_admission_service import build_inventory_capture_admission_bundle
from app.services.menu_coverage_audit_service import (
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
    return_detail_evidence: Path | None
    member_evidence: Path | None
    product_evidence: Path | None
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


def load_return_detail_evidence(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "return-detail-evidence-chain-*.json")
    payload = _load_json(path)
    return path, payload


def load_member_evidence(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "member-evidence-chain-*.json")
    payload = _load_json(path)
    return path, payload


def load_product_evidence(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest_json(analysis_root, "product-evidence-chain-*.json")
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
            "member-capture-research-*.json",
            "product-capture-research-*.json",
            "customer-capture-research-*.json",
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
        if filename.startswith("member-capture-research-"):
            _register("会员中心 / SelVipInfoList", mode="research", payload=payload, path=path)
            continue
        if filename.startswith("product-capture-research-"):
            _register("商品资料 / SelWareList", mode="research", payload=payload, path=path)
            continue
        if filename.startswith("customer-capture-research-"):
            _register("客户资料 / SelDeptList", mode="research", payload=payload, path=path)

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
            "mainline_ready": False,
            "blocking_issues": list(member_center.get("blocking_issues") or []),
            "next_action": "继续从页面控件或接口上下文反推 condition 合法值，并确认是否存在服务端上限，再评估 capture 准入",
            "current_judgment": "会员主数据候选源（空查询可直接返回会员集合，searchval 可用于全局过滤）",
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
    search_behavior = dict((product_list.get("search_behavior") or {}))
    analysis_sources = [_repo_path(product_evidence_path, repo_root)]
    if product_page:
        analysis_sources.append(product_page["_source_path"])
    analysis_sources = list(dict.fromkeys(analysis_sources))

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
            ],
            "research_map_complete": True,
            "ingestion_blocked_by_global_gate": True,
            "mainline_ready": False,
            "blocking_issues": list(product_list.get("blocking_issues") or []),
            "next_action": "继续确认 warecause 的业务范围；若无额外限制，可按大页尺寸顺序翻页进入首批 capture admit",
            "current_judgment": "商品主数据候选源（page 顺序翻页成立，spenum 支持精确搜索）",
            "capture_strategy": "自动翻页",
            "risk_labels": product_route["risk_labels"],
            "ledger_path": product_route["ledger_path"],
            "analysis_sources": analysis_sources,
            "capture_admission_ready": bool(product_list.get("capture_admission_ready")),
            "capture_parameter_plan": dict(product_list.get("capture_parameter_plan") or {}),
            "parameter_semantics": parameter_semantics,
            "pagesize_probe_summary": pagesize_probe_summary,
            "search_behavior": search_behavior,
            **product_coverage,
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
    return_detail_evidence_path, return_detail_evidence = load_return_detail_evidence(analysis_root)
    member_evidence_path, member_evidence = load_member_evidence(analysis_root)
    product_evidence_path, product_evidence = load_product_evidence(analysis_root)
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
        if product_evidence is not None and product_evidence_path is not None and route["title"] == "商品资料":
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
            else:
                entry["blocking_issues"] = [
                    "当前默认参数会触发服务端 SQL 截断错误",
                    "尚未完成 type 合法值集合确认",
                    "尚未确认页面附加参数是否影响服务端查询",
                ]
                entry["next_action"] = "先确认 SelReturnStockList 的 type 参数和页面附加参数，再定位 SQL 截断边界"
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
        return_detail_evidence=return_detail_evidence_path,
        member_evidence=member_evidence_path,
        product_evidence=product_evidence_path,
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
        "return_detail_evidence": _repo_path(sources.return_detail_evidence, repo_root) if sources.return_detail_evidence else None,
        "member_evidence": _repo_path(sources.member_evidence, repo_root) if sources.member_evidence else None,
        "product_evidence": _repo_path(sources.product_evidence, repo_root) if sources.product_evidence else None,
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
