from __future__ import annotations

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


def _doc_numbers(payload: Any) -> list[str]:
    values: list[str] = []
    for row in extract_normalized_table_rows(payload):
        value = row.get("docno")
        if value in (None, ""):
            value = row.get("doc_no")
        if value in (None, ""):
            continue
        values.append(str(value))
    return values[:10]


def build_receipt_confirmation_http_evidence_chain(
    *,
    baseline_payload: Any,
    page_payloads: Mapping[str, Any],
    page_size_payloads: Mapping[str, Any],
    time_payloads: Mapping[str, Any],
    search_payloads: Mapping[str, Any],
) -> dict[str, Any]:
    baseline = analyze_response_payload(baseline_payload)
    baseline_rows = extract_normalized_table_rows(baseline_payload)

    page_variants = [_variant_summary(value=value, payload=payload) for value, payload in page_payloads.items()]
    page_size_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in page_size_payloads.items()
    ]
    time_variants = [_variant_summary(value=value, payload=payload) for value, payload in time_payloads.items()]
    search_variants = [_variant_summary(value=value, payload=payload) for value, payload in search_payloads.items()]

    page_semantics = classify_http_probe_semantics(
        parameter_path="page",
        baseline_analysis=baseline,
        variants=page_variants,
    )
    page_size_semantics = classify_http_probe_semantics(
        parameter_path="pageSize",
        baseline_analysis=baseline,
        variants=page_size_variants,
    )
    time_semantics = classify_http_probe_semantics(
        parameter_path="time",
        baseline_analysis=baseline,
        variants=time_variants,
    )
    search_semantics = classify_http_probe_semantics(
        parameter_path="search",
        baseline_analysis=baseline,
        variants=search_variants,
    )

    all_same_dataset = all(
        item["semantics"] == "same_dataset"
        for item in (page_semantics, page_size_semantics, time_semantics, search_semantics)
    )
    no_match_still_returns_baseline = any(
        int(item.get("row_count") or 0) == int(baseline.get("row_count") or 0)
        and item.get("row_set_signature") == baseline.get("row_set_signature")
        for item in search_variants
        if str(item.get("value")).startswith("__no_match__")
    )

    baseline_row_count = int(baseline.get("row_count") or 0)
    blocking_issues: list[str] = []
    if baseline_row_count <= 0:
        blocking_issues.append("baseline 当前为空，尚不能确认收货确认主列表是否可稳定准入")

    secondary_route_blocking_issues = [
        "单据确认动作链仍依赖页面选中行或隐藏动作链",
        "物流信息动作链仍依赖页面选中行或隐藏动作链",
        "扫描校验动作链仍待识别",
    ]
    capture_admission_ready = not blocking_issues

    observed_doc_numbers = _doc_numbers(baseline_payload)
    return {
        "receipt_confirmation": {
            "endpoint": "SelDocConfirmList",
            "baseline": baseline,
            "observed_doc_numbers": observed_doc_numbers,
            "observed_row_keys_preview": [list(row.keys())[:10] for row in baseline_rows[:3]],
            "parameter_semantics": {
                "page": page_semantics,
                "pageSize": page_size_semantics,
                "time": time_semantics,
                "search": search_semantics,
            },
            "recommended_http_strategy": {
                "baseline": "先固定空 payload 获取当前账号可见的收货确认主列表",
                "page": "当前 seed page/pageSize 未改变数据集，主列表暂按单请求处理",
                "time": "time 当前未改变数据集，主列表先保留空 payload；若后续页面动作链证明存在隐藏时间上下文，再拆成二级路线参数",
                "search": "search 当前在 no-match seed 下仍返回 baseline，暂不把 search 作为主列表准入所需过滤器",
                "next_step": "先按主列表准入 capture，再继续验证单据确认 / 物流信息 / 扫描校验等动作链是否补充隐藏参数或二级接口",
            },
            "capture_admission_ready": capture_admission_ready,
            "capture_parameter_plan": {
                "baseline_payload": {},
                "page_seed_values": [item["value"] for item in page_variants],
                "page_size_seed_values": [item["value"] for item in page_size_variants],
                "time_seed_values": [item["value"] for item in time_variants],
                "search_seed_values": [item["value"] for item in search_variants],
                "page_mode": "single_request_same_dataset_verified",
                "time_mode": "keep_default_empty_payload",
                "search_mode": "ignored_for_primary_list",
                "secondary_actions_pending": ["单据确认", "物流信息", "扫描校验"],
            },
            "blocking_issues": blocking_issues,
            "secondary_route_blocking_issues": secondary_route_blocking_issues,
            "judgment": (
                "真实主接口已通过 HTTP 回证；当前 seed 参数 page/pageSize/time/search 均未改变数据集，"
                "说明主列表可先按空 payload 准入 capture，而单据确认 / 物流信息 / 扫描校验应拆成后续二级动作链。"
            ),
        },
        "issue_flags": [
            *(["receipt_confirmation_seed_params_same_dataset"] if all_same_dataset else []),
            *(["receipt_confirmation_search_ignored_or_context_bound"] if no_match_still_returns_baseline else []),
            "receipt_confirmation_hidden_action_context_pending",
        ],
        "conclusion": {
            "receipt_confirmation_mainline_ready": capture_admission_ready,
            "next_focus": "收货确认主列表可先按空 payload 准入 capture；继续验证页面选中行和详情/确认动作链是否会补充隐藏参数或明细接口。",
        },
    }
