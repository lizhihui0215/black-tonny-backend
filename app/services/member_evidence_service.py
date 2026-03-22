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


def _normalize_filter_semantics(
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
        normalized["recommended_http_strategy"] = "enum_or_scope_sweep"
        normalized["mainline_ready"] = False
        return normalized
    return semantics


def build_member_http_evidence_chain(
    *,
    member_center_baseline_payload: Any,
    member_center_search_payloads: Mapping[str, Any],
    member_center_volume_payloads: Mapping[str, Any],
    member_center_condition_payloads: Mapping[str, Any],
) -> dict[str, Any]:
    baseline = analyze_response_payload(member_center_baseline_payload)

    search_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in member_center_search_payloads.items()
    ]
    volume_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in member_center_volume_payloads.items()
    ]

    condition_probes: list[dict[str, Any]] = []
    valid_condition_values: list[str] = []
    invalid_condition_values: list[str] = []
    for value, payload in member_center_condition_payloads.items():
        error = _extract_error(payload)
        if error is None:
            valid_condition_values.append(str(value))
            probe = {
                "value": value,
                "is_error": False,
                "analysis": analyze_response_payload(payload),
            }
        else:
            invalid_condition_values.append(str(value))
            probe = {
                "value": value,
                "is_error": True,
                **error,
            }
        condition_probes.append(probe)

    search_semantics = classify_http_probe_semantics(
        parameter_path="searchval",
        baseline_analysis=baseline,
        variants=search_variants,
    )
    search_semantics = _normalize_filter_semantics(
        search_semantics,
        baseline_columns_signature=baseline.get("columns_signature"),
    )
    volume_semantics = classify_http_probe_semantics(
        parameter_path="VolumeNumber",
        baseline_analysis=baseline,
        variants=volume_variants,
    )

    zero_match_values = [
        str(item["value"])
        for item in search_variants
        if int(item["row_count"] or 0) == 0
    ]
    exact_match_values = [
        str(item["value"])
        for item in search_variants
        if int(item["row_count"] or 0) == 1
    ]
    broad_same_dataset_values = [
        str(item["value"])
        for item in search_variants
        if item["row_set_signature"] == baseline["row_set_signature"]
    ]

    issue_flags: list[str] = []
    if invalid_condition_values:
        issue_flags.append("member_condition_semantics_unresolved")
    if not valid_condition_values:
        issue_flags.append("member_condition_symbolic_values_rejected")
    if volume_semantics["semantics"] not in {"data_subset_or_scope_switch", "scope_or_date_boundary"}:
        issue_flags.append("member_volume_semantics_pending")

    return {
        "member_center": {
            "endpoint": "SelVipInfoList",
            "baseline": baseline,
            "parameter_semantics": {
                "searchval": search_semantics,
                "VolumeNumber": volume_semantics,
            },
            "search_behavior": {
                "zero_match_values": zero_match_values,
                "exact_match_values": exact_match_values,
                "broad_same_dataset_values": broad_same_dataset_values,
                "default_empty_search_returns_baseline": True,
            },
            "condition_probe_summary": {
                "probes": condition_probes,
                "valid_condition_values": valid_condition_values,
                "invalid_condition_values": invalid_condition_values,
                "all_symbolic_values_rejected": bool(invalid_condition_values) and not valid_condition_values,
            },
            "recommended_http_strategy": {
                "baseline": "固定使用 condition=''、searchval=''、VolumeNumber='' 作为全量主查询",
                "searchval": "searchval 当前表现为全局搜索过滤，适合后续做精确查询或补样，不应改变全量主查询默认值",
                "VolumeNumber": "VolumeNumber 会显著收窄会员集合，暂视为范围过滤参数；在语义坐实前不纳入全量主查询",
                "condition": "condition 当前不能直接填字段名或页面文案值；需继续通过页面动作或接口上下文反推合法取值",
            },
            "capture_admission_ready": False,
            "blocking_issues": [
                issue
                for issue in (
                    "condition 语义仍待确认" if invalid_condition_values else None,
                    "VolumeNumber 的业务语义仍待命名" if volume_semantics["semantics"] == "data_subset_or_scope_switch" else None,
                    "是否存在服务端上限仍待确认",
                )
                if issue is not None
            ],
        },
        "issue_flags": issue_flags,
        "conclusion": {
            "member_center_mainline_ready": False,
            "next_focus": "先通过页面动作或控制配置还原 condition 合法值，再确认 VolumeNumber 的业务语义和潜在服务端上限。",
        },
    }
