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
    }


def build_product_http_evidence_chain(
    *,
    product_baseline_payload: Any,
    product_page_payloads: Mapping[str, Any],
    product_pagesize_payloads: Mapping[str, Any],
    product_spenum_payloads: Mapping[str, Any],
) -> dict[str, Any]:
    baseline = analyze_response_payload(product_baseline_payload)

    page_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in product_page_payloads.items()
    ]
    pagesize_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in product_pagesize_payloads.items()
    ]
    spenum_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in product_spenum_payloads.items()
    ]
    spenum_semantic_variants = [
        item for item in spenum_variants if int(item["row_count"] or 0) > 0
    ]

    page_semantics = classify_http_probe_semantics(
        parameter_path="page",
        baseline_analysis=baseline,
        variants=page_variants,
    )
    spenum_semantics = classify_http_probe_semantics(
        parameter_path="spenum",
        baseline_analysis=baseline,
        variants=spenum_semantic_variants,
    )

    page_sizes = [int(item["value"]) for item in pagesize_variants if item.get("value") is not None]
    row_counts = [int(item["row_count"] or 0) for item in pagesize_variants]
    growth_pairs = list(zip(page_sizes, row_counts, strict=True))
    recommended_pagesize = max(page_sizes) if page_sizes else None
    service_cap_detected = False
    if len(row_counts) >= 2:
        service_cap_detected = any(
            current_rows <= previous_rows
            for previous_rows, current_rows in zip(row_counts, row_counts[1:], strict=False)
        )

    exact_match_values = [
        str(item["value"])
        for item in spenum_variants
        if int(item["row_count"] or 0) == 1
    ]
    broad_match_values = [
        str(item["value"])
        for item in spenum_variants
        if int(item["row_count"] or 0) > 1
    ]
    zero_match_values = [
        str(item["value"])
        for item in spenum_variants
        if int(item["row_count"] or 0) == 0
    ]
    spenum_filter_confirmed = bool(exact_match_values or broad_match_values) and spenum_semantics["semantics"] in {
        "data_subset_or_scope_switch",
        "scope_or_date_boundary",
        "mixed",
    }

    blocking_issues = [
        issue
        for issue in (
            None if page_semantics["semantics"] == "pagination_page_switch" else "page 语义仍待确认",
            None if spenum_filter_confirmed else "spenum 语义仍待确认",
            "warecause 语义仍待确认",
            None if recommended_pagesize is not None else "尚未确认安全的大页尺寸",
            None if not service_cap_detected else "服务端页上限已触发但上限值仍待确认",
        )
        if issue is not None
    ]

    capture_parameter_plan = {
        "default_spenum": "",
        "default_warecause": "",
        "baseline_page": 1,
        "recommended_pagesize": recommended_pagesize,
        "page_mode": "sequential_pagination" if page_semantics["semantics"] == "pagination_page_switch" else "needs_followup",
        "exact_search_examples": exact_match_values,
        "broad_search_examples": broad_match_values,
    }

    capture_admission_ready = (
        page_semantics["semantics"] == "pagination_page_switch"
        and spenum_filter_confirmed
        and recommended_pagesize is not None
        and not blocking_issues
    )

    return {
        "product_list": {
            "endpoint": "SelWareList",
            "baseline": baseline,
            "parameter_semantics": {
                "page": page_semantics,
                "spenum": spenum_semantics,
            },
            "pagesize_probe_summary": {
                "variants": pagesize_variants,
                "tested_page_sizes": page_sizes,
                "max_observed_rows": max(row_counts) if row_counts else 0,
                "recommended_pagesize": recommended_pagesize,
                "service_cap_detected": service_cap_detected,
            },
            "search_behavior": {
                "exact_match_values": exact_match_values,
                "broad_match_values": broad_match_values,
                "zero_match_values": zero_match_values,
            },
            "capture_parameter_plan": capture_parameter_plan,
            "capture_admission_ready": capture_admission_ready,
            "blocking_issues": blocking_issues,
        },
        "issue_flags": [],
        "conclusion": {
            "product_list_mainline_ready": capture_admission_ready,
            "next_focus": (
                "商品资料已确认 page 顺序翻页与 spenum 精确搜索语义；下一步应确认 warecause 作用范围，并把大页尺寸纳入正式 capture admit。"
            ),
        },
    }
