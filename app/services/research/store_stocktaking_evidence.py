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


def _doc_ids(payload: Any) -> list[str]:
    values: list[str] = []
    for row in extract_normalized_table_rows(payload):
        value = row.get("pdid")
        if value in (None, ""):
            continue
        values.append(str(value))
    return values[:10]


def _coerce_empty_variant_semantics(semantics: dict[str, Any], *, category: str, variants: list[dict[str, Any]]) -> dict[str, Any]:
    if semantics.get("semantics") != "mixed":
        return semantics
    row_counts = [int(item.get("row_count") or 0) for item in variants]
    if not row_counts or max(row_counts) <= 0 or min(row_counts) > 0:
        return semantics
    coerced = dict(semantics)
    if category == "enum":
        coerced["semantics"] = "data_subset_or_scope_switch"
        coerced["recommended_http_strategy"] = "enum_or_scope_sweep"
        coerced["mainline_ready"] = False
    else:
        coerced["semantics"] = "scope_or_date_boundary"
        coerced["recommended_http_strategy"] = "date_or_scope_parameter"
        coerced["mainline_ready"] = True
    return coerced


def build_store_stocktaking_http_evidence_chain(
    *,
    baseline_payload: Any,
    stat_payloads: Mapping[str, Any],
    date_payloads: Mapping[str, Any],
) -> dict[str, Any]:
    baseline = analyze_response_payload(baseline_payload)
    stat_variants = [_variant_summary(value=value, payload=payload) for value, payload in stat_payloads.items()]
    date_variants = [_variant_summary(value=value, payload=payload) for value, payload in date_payloads.items()]

    stat_semantics = classify_http_probe_semantics(
        parameter_path="stat",
        baseline_analysis=baseline,
        variants=stat_variants,
    )
    stat_semantics = _coerce_empty_variant_semantics(stat_semantics, category="enum", variants=stat_variants)
    bdate_semantics = classify_http_probe_semantics(
        parameter_path="bdate",
        baseline_analysis=baseline,
        variants=date_variants,
    )
    bdate_semantics = _coerce_empty_variant_semantics(bdate_semantics, category="date", variants=date_variants)

    baseline_row_count = int(baseline.get("row_count") or 0)
    stat_equivalent_values = [
        item["value"]
        for item in stat_variants
        if item.get("row_set_signature") == baseline.get("row_set_signature") and item.get("value") != "stat=A"
    ]
    primary_stat_values = ["A"]
    if "stat=1" in stat_equivalent_values:
        primary_stat_values.append("1")
    excluded_stat_values = [
        item["value"]
        for item in stat_variants
        if item.get("row_set_signature") != baseline.get("row_set_signature")
    ]

    blocking_issues: list[str] = []
    if baseline_row_count <= 0:
        blocking_issues.append("baseline 当前为空，尚不能确认盘点单主列表是否可稳定准入")

    secondary_route_blocking_issues = [
        "查看明细二级接口仍待识别",
        "统计损溢二级接口仍待识别",
        "条码记录二级接口仍待识别",
    ]
    capture_admission_ready = not blocking_issues

    return {
        "store_stocktaking": {
            "endpoint": "SelDocManageList",
            "baseline": baseline,
            "observed_doc_ids": _doc_ids(baseline_payload),
            "parameter_semantics": {
                "stat": stat_semantics,
                "bdate": bdate_semantics,
            },
            "recommended_http_strategy": {
                "baseline": "先固定 bdate/edate 与 stat=A 获取当前账号可见盘点单主列表",
                "stat": "当前 seed 显示 stat=1 与 baseline 等价，stat=0 会收窄为空集；主列表准入先保留 stat=A，并把 stat=1 视为等价备选值",
                "date": "bdate/edate 当前是范围边界参数；主列表准入应固定时间窗口，二级动作链另行拆分",
                "next_step": "先按主列表准入 capture，再继续确认查看明细、条码记录、统计损溢是否拆成独立二级路线。",
            },
            "capture_admission_ready": capture_admission_ready,
            "capture_parameter_plan": {
                "baseline_payload": {
                    "edate": "20260323",
                    "bdate": "20260316",
                    "deptcode": "",
                    "stat": "A",
                    "menuid": "E003002001",
                },
                "stat_seed_values": [item["value"] for item in stat_variants],
                "primary_stat_values": primary_stat_values,
                "equivalent_stat_values": stat_equivalent_values,
                "excluded_stat_values": excluded_stat_values,
                "date_seed_values": [item["value"] for item in date_variants],
                "page_mode": "no_pagination_field_observed",
                "date_window_mode": "fixed_bdate_edate_window",
                "secondary_actions_pending": ["查看明细", "统计损溢", "条码记录"],
            },
            "blocking_issues": blocking_issues,
            "secondary_route_blocking_issues": secondary_route_blocking_issues,
            "judgment": (
                "真实主列表接口已通过 HTTP 回证，当前可稳定返回盘点单主列表；"
                "stat=1 与 baseline 当前等价、stat=0 会收窄为空集，日期范围作为边界参数固定后，"
                "主列表已可单独准入 capture；查看明细、统计损溢、条码记录应拆成后续二级路线。"
            ),
        },
        "issue_flags": [
            "store_stocktaking_main_endpoint_confirmed",
            *(["store_stocktaking_stat_scope_switch"] if stat_semantics["semantics"] != "same_dataset" else []),
            *(["store_stocktaking_date_boundary"] if bdate_semantics["semantics"] == "scope_or_date_boundary" else []),
            "store_stocktaking_detail_chain_pending",
        ],
        "conclusion": {
            "store_stocktaking_mainline_ready": capture_admission_ready,
            "next_focus": "门店盘点单主列表可先按固定 stat/date 窗口准入 capture；继续确认查看明细、条码记录、统计损溢是否拆成独立二级接口。",
        },
    }
