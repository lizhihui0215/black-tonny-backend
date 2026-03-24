from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from app.services.erp_research_service import (
    analyze_response_payload,
    classify_http_probe_semantics,
    extract_normalized_table_rows,
)


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


def _variant_group(value: Any) -> str:
    return str(value).split(":", 1)[0]


def _row_fingerprint_set(payload: Any) -> set[str]:
    return {
        json.dumps(row, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
        for row in extract_normalized_table_rows(payload)
    }


def _normalize_scope_semantics(
    semantics: dict[str, Any],
    *,
    baseline_columns_signature: str | None,
) -> dict[str, Any]:
    if semantics.get("semantics") != "mixed":
        return semantics
    variants = list(semantics.get("variants") or [])
    non_empty_variants = [item for item in variants if int(item.get("row_count") or 0) > 0]
    zero_row_variants = [item for item in variants if int(item.get("row_count") or 0) == 0]
    if (
        non_empty_variants
        and zero_row_variants
        and baseline_columns_signature is not None
        and all(item.get("columns_signature") == baseline_columns_signature for item in non_empty_variants)
    ):
        normalized = dict(semantics)
        normalized["semantics"] = "data_subset_or_scope_switch"
        normalized["recommended_http_strategy"] = "single_request_with_filter_probe"
        normalized["mainline_ready"] = False
        return normalized
    return semantics


def build_stored_value_http_evidence_chain(
    *,
    stored_value_baseline_payload: Any,
    baseline_request_payload: Mapping[str, Any],
    stored_value_search_payloads: Mapping[str, Any],
    stored_value_date_window_payloads: Mapping[str, Any],
    stored_value_partition_payloads: Mapping[str, Any] | None = None,
    date_partition_mode: str | None = None,
) -> dict[str, Any]:
    baseline = analyze_response_payload(stored_value_baseline_payload)
    baseline_row_fingerprint_set = _row_fingerprint_set(stored_value_baseline_payload)

    search_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in stored_value_search_payloads.items()
    ]
    date_window_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in stored_value_date_window_payloads.items()
    ]
    partition_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in (stored_value_partition_payloads or {}).items()
    ]

    search_semantics = classify_http_probe_semantics(
        parameter_path="Search",
        baseline_analysis=baseline,
        variants=search_variants,
    )
    search_semantics = _normalize_scope_semantics(
        search_semantics,
        baseline_columns_signature=baseline.get("columns_signature"),
    )

    date_semantics = classify_http_probe_semantics(
        parameter_path="BeginDate_EndDate",
        baseline_analysis=baseline,
        variants=date_window_variants,
    )
    date_semantics = _normalize_scope_semantics(
        date_semantics,
        baseline_columns_signature=baseline.get("columns_signature"),
    )

    subset_match_values = [
        str(item["value"])
        for item in search_variants
        if 0 < int(item["row_count"] or 0) < int(baseline.get("row_count") or 0)
    ]
    zero_match_values = [
        str(item["value"])
        for item in search_variants
        if int(item["row_count"] or 0) == 0
    ]
    same_dataset_values = [
        str(item["value"])
        for item in search_variants
        if item["row_set_signature"] == baseline.get("row_set_signature")
    ]
    supported_search_groups = {
        _variant_group(item["value"])
        for item in search_variants
        if 0 < int(item["row_count"] or 0) < int(baseline.get("row_count") or 0)
    }
    zero_match_groups = {
        _variant_group(item["value"])
        for item in search_variants
        if int(item["row_count"] or 0) == 0
    }

    partition_union_fingerprints: set[str] = set()
    for payload in (stored_value_partition_payloads or {}).values():
        partition_union_fingerprints |= _row_fingerprint_set(payload)
    partition_union_matches_baseline = bool(partition_variants) and (
        partition_union_fingerprints == baseline_row_fingerprint_set
    )
    partition_missing_row_count = len(baseline_row_fingerprint_set - partition_union_fingerprints)
    partition_extra_row_count = len(partition_union_fingerprints - baseline_row_fingerprint_set)

    search_mode = (
        "vip_card_only_filter"
        if "vip_card_id" in supported_search_groups and not ({"happen_no", "vip_name"} & supported_search_groups)
        else "multi_field_filter"
    )
    page_mode = "single_request_half_open_date_verified" if partition_union_matches_baseline else "single_request_hidden_cap_pending"

    blocking_issues = [
        issue
        for issue in (
            None if subset_match_values else "Search 尚未确认有效收敛值",
            None if "vip_card_id" in supported_search_groups else "Search 当前尚未确认对卡号类值稳定生效",
            None if date_semantics.get("semantics") in {"data_subset_or_scope_switch", "scope_or_date_boundary"} else "BeginDate/EndDate 语义仍待确认",
            None if partition_union_matches_baseline else "尚未确认时间窗口分片与 baseline 的完整覆盖关系",
            None if partition_union_matches_baseline else "尚未确认是否存在隐藏分页或服务端上限",
        )
        if issue is not None
    ]
    capture_admission_ready = not blocking_issues

    return {
        "stored_value_detail": {
            "endpoint": "FXDIYReport/GetDIYReportData",
            "baseline": baseline,
            "parameter_semantics": {
                "Search": search_semantics,
                "BeginDate_EndDate": date_semantics,
            },
            "search_behavior": {
                "subset_match_values": subset_match_values,
                "zero_match_values": zero_match_values,
                "same_dataset_values": same_dataset_values,
                "supported_search_groups": sorted(supported_search_groups),
                "zero_match_groups": sorted(zero_match_groups),
                "vip_card_filter_confirmed": "vip_card_id" in supported_search_groups,
                "happen_no_filter_confirmed": "happen_no" in supported_search_groups,
                "vip_name_filter_confirmed": "vip_name" in supported_search_groups,
            },
            "date_window_probe_summary": {"variants": date_window_variants},
            "date_partition_verification": {
                "partition_mode": date_partition_mode,
                "variants": partition_variants,
                "partition_union_row_count": len(partition_union_fingerprints),
                "partition_union_matches_baseline": partition_union_matches_baseline,
                "partition_missing_row_count": partition_missing_row_count,
                "partition_extra_row_count": partition_extra_row_count,
            },
            "capture_parameter_plan": {
                "default_BeginDate": str(baseline_request_payload.get("BeginDate") or ""),
                "default_EndDate": str(baseline_request_payload.get("EndDate") or ""),
                "default_Search": str(baseline_request_payload.get("Search") or ""),
                "search_mode": search_mode,
                "page_mode": page_mode,
                "date_boundary_mode": date_partition_mode,
                "search_seed_examples": [item["value"] for item in search_variants],
            },
            "capture_admission_ready": capture_admission_ready,
            "blocking_issues": blocking_issues,
            "judgment": (
                "储值卡明细已完成 HTTP 回证，当前可按默认空 Search 单请求进入 capture；Search 已确认只对卡号类值稳定收敛，时间窗口已验证为半开区间。"
                if capture_admission_ready
                else "储值卡明细已完成 HTTP 回证，当前最像储值流水明细主源候选，但仍需确认 Search 语义与隐藏上限。"
            ),
            "non_blocking_findings": [
                *(
                    ["Search 对 HappenNo / VipName 未观察到稳定收敛效果，当前只建议把 Search 作为卡号类过滤器使用。"]
                    if {"happen_no", "vip_name"} & zero_match_groups
                    else []
                ),
            ],
        },
        "issue_flags": [
            *(["stored_value_search_partial_semantics"] if {"happen_no", "vip_name"} & zero_match_groups else []),
            *(["stored_value_hidden_cap_pending"] if not partition_union_matches_baseline else []),
        ],
        "conclusion": {
            "stored_value_detail_mainline_ready": capture_admission_ready,
            "next_focus": (
                "储值卡明细已满足 capture admit 条件，下一步按默认空 Search 单请求准入 capture，并把 Search 语义限制收进文档。"
                if capture_admission_ready
                else "继续确认 Search 是否只对卡号类值生效，以及时间窗口分片是否能完整覆盖 baseline。"
            ),
        },
    }
