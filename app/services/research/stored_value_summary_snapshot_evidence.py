from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.erp_research_service import analyze_response_payload, extract_normalized_table_rows
from app.services.research.product_evidence import extract_declared_total_count


def _summarize_seed_semantics(seed_results: Mapping[str, Any] | None) -> dict[str, Any]:
    seed_results = dict(seed_results or {})
    tested_values = [str(value) for value in seed_results.keys()]
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
    return {
        "tested_values": tested_values,
        "same_dataset_values": same_dataset_values,
        "different_dataset_values": different_dataset_values,
        "error_values": error_values,
    }


def _single_request_page_ignored(
    page_probe_results: Mapping[str, Any] | None,
    observed_total_rows: int,
) -> bool:
    page_probe_results = dict(page_probe_results or {})
    if not page_probe_results:
        return False
    return all(int(page_probe_results.get(key) or -1) == observed_total_rows for key in page_probe_results)


def build_stored_value_card_summary_snapshot_http_evidence_chain(
    *,
    stored_value_card_summary_baseline_payload: Any,
    baseline_request_payload: Mapping[str, Any] | None,
    page_probe_results: Mapping[str, Any] | None = None,
    search_seed_results: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    baseline = analyze_response_payload(stored_value_card_summary_baseline_payload)
    request_payload = dict(baseline_request_payload or {})
    parameter_payload = dict(request_payload.get("parameter") or {})
    observed_total_rows = len(extract_normalized_table_rows(stored_value_card_summary_baseline_payload))
    declared_total_count = extract_declared_total_count(stored_value_card_summary_baseline_payload)
    page_probe_results = dict(page_probe_results or {})
    search_semantics = _summarize_seed_semantics(search_seed_results)

    single_request_complete = declared_total_count is None or observed_total_rows >= declared_total_count
    page_fields_ignored = _single_request_page_ignored(page_probe_results, observed_total_rows)

    blocking_issues = [
        issue
        for issue in (
            None if single_request_complete else "当前单请求返回行数仍低于服务端声明总数",
            None if page_fields_ignored else "尚未确认 page/pagesize 是否仍为同一数据集",
            None if search_semantics["different_dataset_values"] else "尚未确认 Search 是否可以稳定切结果子集",
            None if not search_semantics["error_values"] else f"Search seed 仍有错误值: {', '.join(search_semantics['error_values'])}",
        )
        if issue is not None
    ]
    capture_admission_ready = not blocking_issues

    detail = {
        "endpoint": "GetDIYReportData",
        "baseline": baseline,
        "capture_parameter_plan": {
            "default_menuid": str(request_payload.get("menuid") or ""),
            "default_gridid": str(request_payload.get("gridid") or ""),
            "default_begin_date": str(parameter_payload.get("BeginDate") or ""),
            "default_end_date": str(parameter_payload.get("EndDate") or ""),
            "default_search": str(parameter_payload.get("Search") or ""),
            "request_keys": sorted(str(key) for key in request_payload.keys()),
            "parameter_keys": sorted(str(key) for key in parameter_payload.keys()),
            "page_mode": "single_request_page_field_ignored" if page_fields_ignored else "needs_followup",
            "declared_total_count": declared_total_count,
            "observed_total_rows": observed_total_rows,
            "single_request_complete": single_request_complete,
            "page_probe_results": page_probe_results,
            "search_semantics": search_semantics,
        },
        "capture_page_summary": {
            "request_payload": request_payload,
            "declared_total_count": declared_total_count,
            "observed_total_rows": observed_total_rows,
            "capture_complete": single_request_complete and page_fields_ignored,
        },
        "capture_admission_ready": capture_admission_ready,
        "blocking_issues": blocking_issues,
        "judgment": (
            "储值卡汇总已完成 HTTP 回证；page/pagesize 当前对结果集无影响，默认请求可稳定返回快照，Search 已验证可以切结果子集，可进入 snapshot capture。"
            if capture_admission_ready
            else "储值卡汇总已完成 HTTP 回证，但单请求完整性、page/pagesize 语义或 Search 子集行为仍需继续确认。"
        ),
    }
    return {
        "stored_value_card_summary_snapshot": detail,
        "issue_flags": [],
        "conclusion": {
            "snapshot_capture_ready": capture_admission_ready,
            "next_focus": (
                "储值卡汇总已满足 snapshot capture 条件；下一步按默认 Search 空值单请求写入 capture，并继续保持卡级汇总快照定位。"
                if capture_admission_ready
                else "储值卡汇总已识别真实接口；下一步继续确认 page/pagesize 是否确实被忽略，以及 Search 语义边界。"
            ),
        },
    }


def build_stored_value_by_store_snapshot_http_evidence_chain(
    *,
    stored_value_by_store_baseline_payload: Any,
    baseline_request_payload: Mapping[str, Any] | None,
    page_probe_results: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    baseline = analyze_response_payload(stored_value_by_store_baseline_payload)
    request_payload = dict(baseline_request_payload or {})
    parameter_payload = dict(request_payload.get("parameter") or {})
    observed_total_rows = len(extract_normalized_table_rows(stored_value_by_store_baseline_payload))
    declared_total_count = extract_declared_total_count(stored_value_by_store_baseline_payload)
    page_probe_results = dict(page_probe_results or {})

    single_request_complete = declared_total_count is None or observed_total_rows >= declared_total_count
    page_fields_ignored = _single_request_page_ignored(page_probe_results, observed_total_rows)

    blocking_issues = [
        issue
        for issue in (
            None if single_request_complete else "当前单请求返回行数仍低于服务端声明总数",
            None if page_fields_ignored else "尚未确认 page/pagesize 是否仍为同一数据集",
        )
        if issue is not None
    ]
    capture_admission_ready = not blocking_issues

    detail = {
        "endpoint": "GetDIYReportData",
        "baseline": baseline,
        "capture_parameter_plan": {
            "default_menuid": str(request_payload.get("menuid") or ""),
            "default_gridid": str(request_payload.get("gridid") or ""),
            "default_begin_date": str(parameter_payload.get("BeginDate") or ""),
            "default_end_date": str(parameter_payload.get("EndDate") or ""),
            "request_keys": sorted(str(key) for key in request_payload.keys()),
            "parameter_keys": sorted(str(key) for key in parameter_payload.keys()),
            "page_mode": "single_request_page_field_ignored" if page_fields_ignored else "needs_followup",
            "declared_total_count": declared_total_count,
            "observed_total_rows": observed_total_rows,
            "single_request_complete": single_request_complete,
            "page_probe_results": page_probe_results,
        },
        "capture_page_summary": {
            "request_payload": request_payload,
            "declared_total_count": declared_total_count,
            "observed_total_rows": observed_total_rows,
            "capture_complete": single_request_complete and page_fields_ignored,
        },
        "capture_admission_ready": capture_admission_ready,
        "blocking_issues": blocking_issues,
        "judgment": (
            "储值按店汇总已完成 HTTP 回证；page/pagesize 当前对结果集无影响，默认请求可稳定返回门店级快照，可进入 snapshot capture。"
            if capture_admission_ready
            else "储值按店汇总已完成 HTTP 回证，但单请求完整性或 page/pagesize 语义仍需继续确认。"
        ),
    }
    return {
        "stored_value_by_store_snapshot": detail,
        "issue_flags": [],
        "conclusion": {
            "snapshot_capture_ready": capture_admission_ready,
            "next_focus": (
                "储值按店汇总已满足 snapshot capture 条件；下一步按默认时间窗单请求写入 capture，并继续保持门店级汇总快照定位。"
                if capture_admission_ready
                else "储值按店汇总已识别真实接口；下一步继续确认 page/pagesize 是否确实被忽略。"
            ),
        },
    }
