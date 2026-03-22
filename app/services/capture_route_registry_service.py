from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.services.api_maturity_board_service import build_api_maturity_board

CAPTURE_ROLE_LABELS = {
    "mainline_fact": "主链事实",
    "reconciliation": "对账留痕",
    "research": "研究留痕",
    "snapshot": "快照留痕",
    "exclude": "不进入 capture",
}

CAPTURE_STATUS_LABELS = {
    "ready_for_capture_admission": "可准入 capture",
    "capture_candidate_blocked": "候选但阻塞",
    "research_before_capture": "先继续研究",
    "reconciliation_only": "仅对账留痕",
    "research_capture_only": "仅研究留痕",
    "snapshot_capture_optional": "可选快照留痕",
    "not_planned": "不规划进入 capture",
}

CAPTURE_NAME_OVERRIDES: dict[str, tuple[str, bool, str]] = {
    "SelSaleReport": ("sales_documents_head", True, "head"),
    "GetDIYReportData(E004001008_2)": ("sales_document_lines", True, "line"),
    "sales_reverse_document_lines": ("sales_reverse_document_lines", True, "reverse"),
    "SelDeptSaleList": ("sales_reconciliation_detail_stats", False, "reconciliation"),
    "库存明细统计 / SelDeptStockWaitList": ("inventory_stock_wait_lines", True, "stock"),
    "出入库单据 / SelOutInStockReport": ("inventory_inout_documents", True, "document"),
    "商品资料 / SelWareList": ("product_master_records", True, "master"),
    "客户资料 / SelDeptList": ("customer_master_records", False, "raw"),
    "会员中心 / SelVipInfoList": ("member_profile_records", False, "raw"),
    "会员维护 / 待识别": ("member_maintenance_records", False, "raw"),
    "储值卡明细 / GetDIYReportData": ("stored_value_card_detail", False, "raw"),
    "退货明细 / SelReturnStockList": ("return_document_lines", False, "raw"),
    "收货确认 / GetViewGridList": ("receipt_confirmation_documents", False, "raw"),
    "门店盘点单 / GetViewGridList": ("store_stocktaking_documents", False, "raw"),
    "每日流水单 / SelectRetailDocPaymentSlip": ("daily_payment_slips_snapshot", False, "snapshot"),
}

GENERIC_ENDPOINT_NAMES = {"GetDIYReportData", "GetViewGridList", "page_baseline", "待识别"}


def _short_endpoint(endpoint: str) -> str:
    endpoint = str(endpoint or "").strip().strip("`")
    if "/" not in endpoint:
        return endpoint
    return endpoint.rsplit("/", 1)[-1]


def _slugify(text: str) -> str:
    lowered = text.lower().strip()
    lowered = re.sub(r"[^a-z0-9]+", "_", lowered)
    lowered = re.sub(r"_+", "_", lowered).strip("_")
    return lowered


def _fallback_capture_route_name(entry: dict[str, Any]) -> str:
    endpoint = _short_endpoint(entry.get("endpoint") or "")
    title = str(entry.get("title") or entry.get("route") or "")
    domain = str(entry.get("domain") or "route")
    endpoint_slug = _slugify(endpoint)
    title_slug = _slugify(title)
    if endpoint_slug and endpoint not in GENERIC_ENDPOINT_NAMES:
        base = f"{domain}_{endpoint_slug}"
    elif title_slug:
        base = f"{domain}_{title_slug}"
    else:
        base = f"{domain}_route"
    digest = hashlib.sha1(str(entry.get("route") or title).encode("utf-8")).hexdigest()[:8]
    return f"{base}_{digest}"


def _capture_role(entry: dict[str, Any]) -> str:
    source_kind = entry["source_kind"]
    if source_kind == "未采纳":
        return "exclude"
    if source_kind == "结果快照":
        return "snapshot"
    if source_kind == "对账源":
        return "reconciliation"
    if source_kind == "研究留痕":
        return "research"
    return "mainline_fact"


def _capture_status(entry: dict[str, Any], capture_role: str) -> str:
    if capture_role == "exclude":
        return "not_planned"
    if capture_role == "snapshot":
        return "snapshot_capture_optional"
    if capture_role == "reconciliation":
        return "reconciliation_only"
    if capture_role == "research":
        return "research_capture_only"
    if entry["stage"] == "已HTTP回证" and not entry["blocking_issues"] and not entry["ingestion_blocked_by_global_gate"]:
        return "ready_for_capture_admission"
    if entry["stage"] == "已HTTP回证":
        return "capture_candidate_blocked"
    return "research_before_capture"


def _capture_wave(entry: dict[str, Any], capture_role: str) -> str:
    if capture_role == "exclude":
        return "exclude"
    if capture_role == "snapshot":
        return "snapshot_optional"
    if capture_role in {"reconciliation", "research"}:
        return "research_only"
    return {
        "sales": "wave_1_sales",
        "inventory": "wave_2_inventory",
        "member": "wave_3_member",
        "stored_value": "wave_3_stored_value",
        "payment_and_docs": "wave_3_payment_and_docs",
    }.get(entry["domain"], "wave_unknown")


def _route_binding(entry: dict[str, Any]) -> dict[str, Any]:
    capture_role = _capture_role(entry)
    override = CAPTURE_NAME_OVERRIDES.get(entry["route"])
    if override:
        capture_route_name, confirmed, route_kind = override
    else:
        capture_route_name = None if capture_role == "exclude" else _fallback_capture_route_name(entry)
        confirmed = False
        route_kind = {
            "mainline_fact": "raw",
            "reconciliation": "reconciliation",
            "research": "research",
            "snapshot": "snapshot",
            "exclude": "excluded",
        }[capture_role]

    status = _capture_status(entry, capture_role)
    return {
        "domain": entry["domain"],
        "domain_label": entry["domain_label"],
        "route": entry["route"],
        "title": entry.get("title"),
        "endpoint": entry.get("endpoint"),
        "menu_path": entry.get("menu_path") or [],
        "source_kind": entry["source_kind"],
        "stage": entry["stage"],
        "reliability_status": entry["reliability_status"],
        "research_map_complete": entry["research_map_complete"],
        "mainline_ready": entry["mainline_ready"],
        "capture_role": capture_role,
        "capture_role_label": CAPTURE_ROLE_LABELS[capture_role],
        "capture_status": status,
        "capture_status_label": CAPTURE_STATUS_LABELS[status],
        "capture_route_name": capture_route_name,
        "capture_route_confirmed": confirmed,
        "route_kind": route_kind,
        "planned_capture_wave": _capture_wave(entry, capture_role),
        "blocking_issues": list(entry["blocking_issues"]),
        "next_action": entry["next_action"],
        "global_gate_blocked": entry["ingestion_blocked_by_global_gate"],
        "usable_raw_data": capture_role != "exclude",
        "analysis_sources": list(entry.get("analysis_sources") or []),
        "capture_parameter_plan": dict(entry.get("capture_parameter_plan") or {}),
        "capture_written_once": bool(entry.get("capture_written_once")),
        "latest_capture_batch_id": entry.get("latest_capture_batch_id"),
        "latest_capture_mode": entry.get("latest_capture_mode"),
        "latest_capture_artifact": entry.get("latest_capture_artifact"),
    }


def build_capture_route_registry_from_board(board: dict[str, Any]) -> dict[str, Any]:
    bindings = [_route_binding(entry) for entry in board["entries"]]
    bindings.sort(key=lambda item: (item["domain"], item["planned_capture_wave"], item["route"]))

    role_counts = Counter(item["capture_role"] for item in bindings)
    status_counts = Counter(item["capture_status"] for item in bindings)
    wave_counts = Counter(item["planned_capture_wave"] for item in bindings)

    blockers_by_wave: dict[str, list[str]] = defaultdict(list)
    for item in bindings:
        if item["blocking_issues"]:
            blockers_by_wave[item["planned_capture_wave"]].extend(item["blocking_issues"])

    summary = {
        "total_routes": len(bindings),
        "usable_raw_route_count": sum(1 for item in bindings if item["usable_raw_data"]),
        "confirmed_capture_route_count": sum(1 for item in bindings if item["capture_route_confirmed"]),
        "ready_for_capture_admission_count": status_counts.get("ready_for_capture_admission", 0),
        "captured_once_count": sum(1 for item in bindings if item["capture_written_once"]),
        "role_counts": dict(role_counts),
        "status_counts": dict(status_counts),
        "wave_counts": dict(wave_counts),
        "top_wave_blockers": {
            wave: dict(Counter(issues).most_common(5))
            for wave, issues in blockers_by_wave.items()
        },
        "global_gate_complete": board["summary"]["global_risk_map_complete"],
    }

    return {
        "summary": summary,
        "routes": bindings,
        "source_board_summary": board["summary"],
        "capture_principles": [
            "所有 usable_raw_data=true 的路线，都必须在 capture 层拥有一条 1:1 的 route 绑定。",
            "只有 ready_for_capture_admission 的路线，才允许进入正式 capture 主链。",
            "reconciliation / research / snapshot 路线可以留痕，但默认不进入 serving 主链。",
            "未采纳路线不进入 capture。",
        ],
    }


def build_capture_route_registry(repo_root: Path, analysis_root: Path) -> dict[str, Any]:
    board = build_api_maturity_board(repo_root, analysis_root)
    return build_capture_route_registry_from_board(board)


def render_capture_route_registry_markdown(registry: dict[str, Any]) -> str:
    summary = registry["summary"]
    lines = [
        "# ERP Capture 路线注册表",
        "",
        "> 本文件由 `scripts/build_erp_capture_route_registry.py` 生成，用来定义“当前账号可见全域路线在 capture 层如何 1:1 落位”。",
        "",
        "## 1. 当前目标",
        "",
        "- 让所有 `usable_raw_data=true` 的路线在 capture 层都有明确落位，而不是只在文档里停留在“研究过”。",
        "- `capture` 先承担原始留痕与回放职责，`serving` 仍然只接已通过二次准入的路线。",
        "- 这份注册表只回答“怎么落 capture、现在处于什么状态”，不替代 API 成熟度状态板。",
        "",
        "## 2. 注册原则",
        "",
    ]
    for item in registry["capture_principles"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 3. 当前总体状态",
            "",
            f"- 路线总数：`{summary['total_routes']}`",
            f"- 可用原始路线：`{summary['usable_raw_route_count']}`",
            f"- 已确认 capture 路线名：`{summary['confirmed_capture_route_count']}`",
            f"- 可准入 capture：`{summary['ready_for_capture_admission_count']}`",
            f"- 已真实写入 capture：`{summary['captured_once_count']}`",
            f"- 全域门槛已达成：`{'是' if summary['global_gate_complete'] else '否'}`",
            "",
            "按 capture 角色：",
        ]
    )
    for role, count in summary["role_counts"].items():
        lines.append(f"- `{CAPTURE_ROLE_LABELS.get(role, role)}`：`{count}`")
    lines.extend(["", "按当前状态："])
    for status, count in summary["status_counts"].items():
        lines.append(f"- `{CAPTURE_STATUS_LABELS.get(status, status)}`：`{count}`")

    lines.extend(
        [
            "",
            "## 4. 路线注册表",
            "",
            "| 路线 | 来源分类 | Capture角色 | Capture状态 | Capture Route | 已确认 | route_kind | 已写capture | 最新batch | 参数计划 | Wave | 菜单路径 | 剩余问题 | 下一步 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in registry["routes"]:
        blockers = "；".join(item["blocking_issues"]) if item["blocking_issues"] else "-"
        menu_path = " / ".join(item["menu_path"]) or "-"
        capture_name = item["capture_route_name"] or "-"
        latest_batch = item.get("latest_capture_batch_id") or "-"
        parameter_plan = item.get("capture_parameter_plan") or {}
        parameter_plan_summary = "；".join(f"{key}={value}" for key, value in parameter_plan.items()) if parameter_plan else "-"
        lines.append(
            f"| {item['route']} | {item['source_kind']} | {item['capture_role_label']} | {item['capture_status_label']} | "
            f"`{capture_name}` | {'是' if item['capture_route_confirmed'] else '否'} | `{item['route_kind']}` | "
            f"{'是' if item['capture_written_once'] else '否'} | `{latest_batch}` | {parameter_plan_summary} | "
            f"`{item['planned_capture_wave']}` | {menu_path} | {blockers} | {item['next_action']} |"
        )

    lines.extend(["", "## 5. Wave Blocker 摘要", ""])
    for wave, blockers in summary["top_wave_blockers"].items():
        lines.append(f"### `{wave}`")
        lines.append("")
        if not blockers:
            lines.append("- 无")
            lines.append("")
            continue
        for blocker, count in blockers.items():
            lines.append(f"- `{count}` 次：{blocker}")
        lines.append("")

    return "\n".join(lines)
