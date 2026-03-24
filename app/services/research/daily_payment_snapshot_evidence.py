from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.erp_research_service import analyze_response_payload, extract_normalized_table_rows


def build_daily_payment_snapshot_http_evidence_chain(
    *,
    daily_payment_baseline_payload: Any,
    baseline_request_payload: Mapping[str, Any] | None,
    searchtype_seed_results: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    baseline = analyze_response_payload(daily_payment_baseline_payload)
    request_payload = dict(baseline_request_payload or {})
    observed_total_rows = len(extract_normalized_table_rows(daily_payment_baseline_payload))
    pagination_keys = [key for key in request_payload if str(key).lower() in {"page", "pagesize", "pageindex", "pageno"}]

    seed_results = dict(searchtype_seed_results or {})
    same_dataset_values = sorted(
        str(seed)
        for seed, detail in seed_results.items()
        if isinstance(detail, Mapping) and str(detail.get("semantics") or "") == "same_dataset"
    )
    different_dataset_values = sorted(
        str(seed)
        for seed, detail in seed_results.items()
        if isinstance(detail, Mapping) and str(detail.get("semantics") or "") == "different_dataset"
    )
    error_values = sorted(
        str(seed)
        for seed, detail in seed_results.items()
        if isinstance(detail, Mapping) and str(detail.get("semantics") or "") == "error"
    )
    tested_values = [str(value) for value in seed_results.keys()]

    searchtype_semantics = {
        "tested_values": tested_values,
        "same_dataset_values": same_dataset_values,
        "different_dataset_values": different_dataset_values,
        "error_values": error_values,
        "same_dataset_for_tested_values": bool(tested_values)
        and len(same_dataset_values) == len(tested_values)
        and not different_dataset_values
        and not error_values,
    }

    blocking_issues = [
        issue
        for issue in (
            None if not pagination_keys else f"请求仍包含分页字段: {', '.join(sorted(pagination_keys))}",
            None if not tested_values else (None if searchtype_semantics["same_dataset_for_tested_values"] else "SearchType seed 当前仍未收成同一数据集"),
            None if not error_values else f"SearchType seed 仍有错误值: {', '.join(error_values)}",
        )
        if issue is not None
    ]
    capture_admission_ready = not blocking_issues

    detail = {
        "endpoint": "SelectRetailDocPaymentSlip",
        "baseline": baseline,
        "capture_parameter_plan": {
            "default_menu_id": str(request_payload.get("MenuID") or ""),
            "default_search_type": str(request_payload.get("SearchType") or ""),
            "default_search": str(request_payload.get("Search") or ""),
            "default_last_date": str(request_payload.get("LastDate") or ""),
            "default_begin_date": str(request_payload.get("BeginDate") or ""),
            "default_end_date": str(request_payload.get("EndDate") or ""),
            "request_keys": sorted(str(key) for key in request_payload.keys()),
            "page_mode": "single_request_no_pagination_fields" if not pagination_keys else "needs_followup",
            "observed_total_rows": observed_total_rows,
            "searchtype_semantics": searchtype_semantics,
        },
        "capture_page_summary": {
            "request_payload": request_payload,
            "observed_total_rows": observed_total_rows,
            "capture_complete": not pagination_keys,
        },
        "capture_admission_ready": capture_admission_ready,
        "blocking_issues": blocking_issues,
        "judgment": (
            "每日流水单已完成 HTTP 回证；默认窗口单请求返回稳定快照，且 SearchType 已验证为同一数据集，可进入 snapshot capture。"
            if capture_admission_ready
            else "每日流水单已完成 HTTP 回证，但 SearchType 或分页边界仍需继续确认。"
        ),
    }
    return {
        "daily_payment_snapshot": detail,
        "issue_flags": [],
        "conclusion": {
            "snapshot_capture_ready": capture_admission_ready,
            "next_focus": (
                "每日流水单已满足 snapshot capture 条件；下一步按默认窗口单请求写入 capture，并继续保持结果快照定位。"
                if capture_admission_ready
                else "每日流水单已识别真实接口；下一步继续确认 SearchType 枚举与分页边界，再决定是否进入 snapshot capture。"
            ),
        },
    }
