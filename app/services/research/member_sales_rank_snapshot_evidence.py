from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.erp_research_service import analyze_response_payload, extract_normalized_table_rows
from app.services.research.product_evidence import extract_declared_total_count


def build_member_sales_rank_snapshot_http_evidence_chain(
    *,
    member_sales_rank_baseline_payload: Any,
    baseline_request_payload: Mapping[str, Any] | None,
    page_probe_results: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    baseline = analyze_response_payload(member_sales_rank_baseline_payload)
    request_payload = dict(baseline_request_payload or {})
    observed_total_rows = len(extract_normalized_table_rows(member_sales_rank_baseline_payload))
    declared_total_count = extract_declared_total_count(member_sales_rank_baseline_payload)
    page_probe_results = dict(page_probe_results or {})

    page_zero_full_fetch = bool(
        page_probe_results.get("page_0_pagesize_20_rows", 0) == observed_total_rows
        and page_probe_results.get("page_1_pagesize_20_rows", 0) < observed_total_rows
    )
    single_request_complete = declared_total_count is None or observed_total_rows >= declared_total_count

    blocking_issues = [
        issue
        for issue in (
            None if single_request_complete else "当前单请求返回行数仍低于服务端声明总数",
            None if page_zero_full_fetch else "尚未确认 page=0 是否稳定触发全量模式",
        )
        if issue is not None
    ]
    capture_admission_ready = not blocking_issues

    detail = {
        "endpoint": "SelVipSaleRank",
        "baseline": baseline,
        "capture_parameter_plan": {
            "default_bdate": str(request_payload.get("bdate") or ""),
            "default_edate": str(request_payload.get("edate") or ""),
            "default_page": int(request_payload.get("page") or 0),
            "default_pagesize": int(request_payload.get("pagesize") or 0),
            "request_keys": sorted(str(key) for key in request_payload.keys()),
            "page_mode": "page_zero_full_fetch" if page_zero_full_fetch else "needs_followup",
            "declared_total_count": declared_total_count,
            "observed_total_rows": observed_total_rows,
            "single_request_complete": single_request_complete,
            "page_probe_results": page_probe_results,
        },
        "capture_page_summary": {
            "request_payload": request_payload,
            "declared_total_count": declared_total_count,
            "observed_total_rows": observed_total_rows,
            "capture_complete": single_request_complete and page_zero_full_fetch,
        },
        "capture_admission_ready": capture_admission_ready,
        "blocking_issues": blocking_issues,
        "judgment": (
            "会员消费排行已完成 HTTP 回证；page=0 当前稳定触发全量模式，且默认请求返回行数已匹配 Count，可进入 snapshot capture。"
            if capture_admission_ready
            else "会员消费排行已完成 HTTP 回证，但当前仍需继续确认 page=0 全量模式或单请求覆盖完整性。"
        ),
    }
    return {
        "member_sales_rank_snapshot": detail,
        "issue_flags": [],
        "conclusion": {
            "snapshot_capture_ready": capture_admission_ready,
            "next_focus": (
                "会员消费排行已满足 snapshot capture 条件；下一步按 page=0 单请求写入 capture，并继续保持排行快照定位。"
                if capture_admission_ready
                else "会员消费排行已识别真实接口；下一步继续确认 page=0 全量模式与单请求覆盖完整性。"
            ),
        },
    }
