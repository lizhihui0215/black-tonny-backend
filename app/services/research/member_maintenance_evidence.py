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


def _extract_error(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    errcode = payload.get("errcode")
    errmsg = payload.get("errmsg")
    if errcode in (None, "") and errmsg in (None, ""):
        return None
    return {
        "errcode": str(errcode) if errcode not in (None, "") else None,
        "errmsg": str(errmsg) if errmsg not in (None, "") else None,
    }


def build_member_maintenance_http_evidence_chain(
    *,
    member_maintenance_baseline_payload: Any,
    member_maintenance_page_payloads: Mapping[str, Any],
    member_maintenance_pagesize_payloads: Mapping[str, Any],
    member_maintenance_search_payloads: Mapping[str, Any],
    member_maintenance_type_payloads: Mapping[str, Any],
    member_maintenance_bdate_payloads: Mapping[str, Any],
    member_maintenance_brdate_payloads: Mapping[str, Any],
) -> dict[str, Any]:
    baseline = analyze_response_payload(member_maintenance_baseline_payload)
    baseline_error = _extract_error(member_maintenance_baseline_payload) or {}

    page_variants = [_variant_summary(value=value, payload=payload) for value, payload in member_maintenance_page_payloads.items()]
    pagesize_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in member_maintenance_pagesize_payloads.items()
    ]
    search_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in member_maintenance_search_payloads.items()
    ]
    type_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in member_maintenance_type_payloads.items()
    ]
    bdate_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in member_maintenance_bdate_payloads.items()
    ]
    brdate_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in member_maintenance_brdate_payloads.items()
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
        parameter_path="search",
        baseline_analysis=baseline,
        variants=search_variants,
    )
    type_semantics = classify_http_probe_semantics(
        parameter_path="type",
        baseline_analysis=baseline,
        variants=type_variants,
    )
    bdate_semantics = classify_http_probe_semantics(
        parameter_path="bdate/edate",
        baseline_analysis=baseline,
        variants=bdate_variants,
    )
    brdate_semantics = classify_http_probe_semantics(
        parameter_path="brdate/erdate",
        baseline_analysis=baseline,
        variants=brdate_variants,
    )

    stable_empty_dataset = (
        int(baseline.get("row_count") or 0) == 0
        and all(
            semantics.get("semantics") == "same_dataset"
            for semantics in (
                page_semantics,
                pagesize_semantics,
                search_semantics,
                type_semantics,
                bdate_semantics,
                brdate_semantics,
            )
        )
    )

    issue_flags: list[str] = []
    if int(baseline.get("row_count") or 0) == 0:
        issue_flags.append("member_maintenance_empty_baseline")
    if stable_empty_dataset:
        issue_flags.append("member_maintenance_stable_empty_dataset_verified")
    if baseline_error:
        issue_flags.append("member_maintenance_baseline_has_error_code")

    return {
        "member_maintenance": {
            "endpoint": "SelVipReturnVisitList",
            "baseline": baseline,
            "parameter_semantics": {
                "page": page_semantics,
                "pagesize": pagesize_semantics,
                "search": search_semantics,
                "type": type_semantics,
                "bdate/edate": bdate_semantics,
                "brdate/erdate": brdate_semantics,
            },
            "capture_parameter_plan": {
                "default_search": "",
                "default_type": "",
                "default_bdate": "",
                "default_edate": "",
                "default_brdate": "",
                "default_erdate": "",
                "baseline_page": 1,
                "baseline_pagesize": 20,
                "page_mode": "single_request_stable_empty_verified" if stable_empty_dataset else "needs_followup",
                "empty_dataset_confirmed": stable_empty_dataset,
            },
            "capture_admission_ready": stable_empty_dataset,
            "blocking_issues": [],
        },
        "issue_flags": issue_flags,
        "conclusion": {
            "member_maintenance_mainline_ready": stable_empty_dataset,
            "next_focus": "当前账号下会员维护已验证为稳定空集，可直接进入 capture admit。"
            if stable_empty_dataset
            else "继续确认会员维护 baseline 空集是否长期稳定，并判断是否需要额外 scope 参数。",
        },
    }
