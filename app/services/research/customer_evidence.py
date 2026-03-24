from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.erp_research_service import analyze_response_payload, classify_http_probe_semantics


def _variant_summary(*, value: Any, payload: Any) -> dict[str, Any]:
    analysis = analyze_response_payload(payload)
    return {
        "value": value,
        "row_count": analysis["row_count"],
        "columns_signature": analysis["columns_signature"],
        "row_set_signature": analysis["row_set_signature"],
        "response_shape": analysis["response_shape"],
        "error_code": analysis.get("error_code"),
        "error_message": analysis.get("error_message"),
    }


def build_customer_http_evidence_chain(
    *,
    customer_baseline_payload: Any,
    customer_page_payloads: Mapping[str, Any],
    customer_pagesize_payloads: Mapping[str, Any],
    customer_search_payloads: Mapping[str, Any],
) -> dict[str, Any]:
    baseline = analyze_response_payload(customer_baseline_payload)

    page_variants = [_variant_summary(value=value, payload=payload) for value, payload in customer_page_payloads.items()]
    pagesize_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in customer_pagesize_payloads.items()
    ]
    search_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in customer_search_payloads.items()
    ]

    page_semantics = classify_http_probe_semantics(
        parameter_path="page",
        baseline_analysis=baseline,
        variants=page_variants,
    )
    pagesize_semantics = classify_http_probe_semantics(
        parameter_path="pagesize",
        baseline_analysis=baseline,
        variants=pagesize_variants,
    )
    search_semantics = classify_http_probe_semantics(
        parameter_path="deptname",
        baseline_analysis=baseline,
        variants=search_variants,
    )

    stable_empty_dataset = (
        int(baseline.get("row_count") or 0) == 0
        and page_semantics.get("semantics") == "same_dataset"
        and pagesize_semantics.get("semantics") == "same_dataset"
        and search_semantics.get("semantics") == "same_dataset"
    )

    issue_flags: list[str] = []
    if int(baseline.get("row_count") or 0) == 0:
        issue_flags.append("customer_empty_baseline")
    if stable_empty_dataset:
        issue_flags.append("customer_stable_empty_dataset_verified")

    return {
        "customer_list": {
            "endpoint": "SelDeptList",
            "baseline": baseline,
            "parameter_semantics": {
                "page": page_semantics,
                "pagesize": pagesize_semantics,
                "deptname": search_semantics,
            },
            "capture_parameter_plan": {
                "default_deptname": "",
                "baseline_page": 1,
                "baseline_pagesize": 20,
                "page_mode": "single_request_stable_empty_verified" if stable_empty_dataset else "needs_followup",
                "empty_dataset_confirmed": stable_empty_dataset,
            },
            "capture_admission_ready": stable_empty_dataset,
            "blocking_issues": [],
            "judgment": (
                "客户资料已完成 HTTP 回证；当前账号下 baseline 为空，且 page/pagesize/deptname 均保持 same_dataset，可按稳定空集路线进入 capture。"
                if stable_empty_dataset
                else "客户资料已完成 HTTP 回证，但当前仍需确认 baseline 空集是否长期稳定。"
            ),
        },
        "issue_flags": issue_flags,
        "conclusion": {
            "customer_mainline_ready": stable_empty_dataset,
            "next_focus": "当前账号下客户资料已验证为稳定空集，可直接进入 capture admit。"
            if stable_empty_dataset
            else "继续确认客户资料 baseline 空集是否长期稳定，并判断是否需要多角色复核。",
        },
    }
