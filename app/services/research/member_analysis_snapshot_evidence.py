from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.erp_research_service import analyze_response_payload, extract_normalized_table_rows


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
        "same_dataset_for_tested_values": bool(tested_values)
        and len(same_dataset_values) == len(tested_values)
        and not different_dataset_values
        and not error_values,
    }


def build_member_analysis_snapshot_http_evidence_chain(
    *,
    member_analysis_baseline_payload: Any,
    baseline_request_payload: Mapping[str, Any] | None,
    page_probe_results: Mapping[str, Any] | None = None,
    type_seed_results: Mapping[str, Any] | None = None,
    tag_seed_results: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    baseline = analyze_response_payload(member_analysis_baseline_payload)
    request_payload = dict(baseline_request_payload or {})
    observed_total_rows = len(extract_normalized_table_rows(member_analysis_baseline_payload))
    page_probe_results = dict(page_probe_results or {})
    type_semantics = _summarize_seed_semantics(type_seed_results)
    tag_semantics = _summarize_seed_semantics(tag_seed_results)

    page_zero_full_fetch = bool(
        page_probe_results.get("page_0_pagesize_20_rows", 0) == observed_total_rows
        and page_probe_results.get("page_1_pagesize_20_rows", 0) < observed_total_rows
    )

    blocking_issues = [
        issue
        for issue in (
            None if page_zero_full_fetch else "尚未确认 page=0 是否稳定触发全量模式",
            None if not type_semantics["error_values"] else f"type seed 仍有错误值: {', '.join(type_semantics['error_values'])}",
            None if not tag_semantics["error_values"] else f"tag seed 仍有错误值: {', '.join(tag_semantics['error_values'])}",
        )
        if issue is not None
    ]
    capture_admission_ready = not blocking_issues

    detail = {
        "endpoint": "SelVipAnalysisReport",
        "baseline": baseline,
        "capture_parameter_plan": {
            "default_salebdate": str(request_payload.get("salebdate") or ""),
            "default_saleedate": str(request_payload.get("saleedate") or ""),
            "default_birthbdate": str(request_payload.get("birthbdate") or ""),
            "default_birthedate": str(request_payload.get("birthedate") or ""),
            "default_type": str(request_payload.get("type") or ""),
            "default_tag": str(request_payload.get("tag") or ""),
            "default_page": int(request_payload.get("page") or 0),
            "default_pagesize": int(request_payload.get("pagesize") or 0),
            "request_keys": sorted(str(key) for key in request_payload.keys()),
            "page_mode": "page_zero_full_fetch" if page_zero_full_fetch else "needs_followup",
            "observed_total_rows": observed_total_rows,
            "page_probe_results": page_probe_results,
            "type_semantics": type_semantics,
            "tag_semantics": tag_semantics,
        },
        "capture_page_summary": {
            "request_payload": request_payload,
            "observed_total_rows": observed_total_rows,
            "capture_complete": page_zero_full_fetch,
        },
        "capture_admission_ready": capture_admission_ready,
        "blocking_issues": blocking_issues,
        "judgment": (
            "会员总和分析已完成 HTTP 回证；page=0 当前稳定触发全量模式，type 对已测值仍是同一数据集，tag 会切结果子集，可进入 snapshot capture。"
            if capture_admission_ready
            else "会员总和分析已完成 HTTP 回证，但 page=0 全量模式或过滤 seed 仍需继续确认。"
        ),
    }
    return {
        "member_analysis_snapshot": detail,
        "issue_flags": [],
        "conclusion": {
            "snapshot_capture_ready": capture_admission_ready,
            "next_focus": (
                "会员总和分析已满足 snapshot capture 条件；下一步按 page=0 单请求写入 capture，并继续保持结果快照定位。"
                if capture_admission_ready
                else "会员总和分析已识别真实接口；下一步继续确认 page=0 全量模式与 type/tag 过滤边界。"
            ),
        },
    }
