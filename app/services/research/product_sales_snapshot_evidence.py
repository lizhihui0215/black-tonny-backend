from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.erp_research_service import analyze_response_payload, extract_normalized_table_rows
from app.services.research.product_evidence import extract_declared_total_count


def build_product_sales_snapshot_http_evidence_chain(
    *,
    product_sales_baseline_payload: Any,
    baseline_request_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    baseline = analyze_response_payload(product_sales_baseline_payload)
    request_payload = dict(baseline_request_payload or {})
    observed_total_rows = len(extract_normalized_table_rows(product_sales_baseline_payload))
    declared_total_count = extract_declared_total_count(product_sales_baseline_payload)
    single_request_complete = declared_total_count is None or observed_total_rows >= declared_total_count

    blocking_issues = [issue for issue in (None if single_request_complete else "当前单请求返回行数仍低于服务端声明总数",) if issue is not None]
    capture_admission_ready = not blocking_issues

    detail = {
        "endpoint": "SelSaleReportData",
        "baseline": baseline,
        "capture_parameter_plan": {
            "default_bdate": str(request_payload.get("bdate") or ""),
            "default_edate": str(request_payload.get("edate") or ""),
            "default_warecause": str(request_payload.get("warecause") or ""),
            "default_spenum": str(request_payload.get("spenum") or ""),
            "request_keys": sorted(str(key) for key in request_payload.keys()),
            "page_mode": "single_request_declared_total_match" if single_request_complete else "needs_followup",
            "declared_total_count": declared_total_count,
            "observed_total_rows": observed_total_rows,
            "single_request_complete": single_request_complete,
        },
        "capture_page_summary": {
            "request_payload": request_payload,
            "declared_total_count": declared_total_count,
            "observed_total_rows": observed_total_rows,
            "capture_complete": single_request_complete,
        },
        "capture_admission_ready": capture_admission_ready,
        "blocking_issues": blocking_issues,
        "judgment": (
            "商品销售情况已完成 HTTP 回证，当前更像商品维度聚合结果快照；默认时间窗单请求返回行数已匹配服务端声明总数，可进入 snapshot capture。"
            if capture_admission_ready
            else "商品销售情况已完成 HTTP 回证，但当前仍需继续确认单请求是否覆盖服务端声明总数。"
        ),
    }
    return {
        "product_sales_snapshot": detail,
        "issue_flags": [],
        "conclusion": {
            "snapshot_capture_ready": capture_admission_ready,
            "next_focus": (
                "商品销售情况已满足 snapshot capture 条件；下一步按默认时间窗单请求写入 capture，并继续保持结果快照定位。"
                if capture_admission_ready
                else "商品销售情况已识别真实接口；下一步继续确认单请求覆盖完整性，再决定是否进入 snapshot capture。"
            ),
        },
    }
