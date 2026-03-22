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


def _signature_group_summary(variants: list[dict[str, Any]]) -> dict[str, Any]:
    signature_groups: dict[str, list[str]] = {}
    for item in variants:
        signature = str(item["row_set_signature"])
        signature_groups.setdefault(signature, []).append(str(item["value"]))
    ordered_groups = list(signature_groups.values())
    return {
        "tested_values": [str(item["value"]) for item in variants],
        "signature_groups": ordered_groups,
        "recommended_distinct_values": [group[0] for group in ordered_groups if group],
        "equivalent_value_groups": [group for group in ordered_groups if len(group) > 1],
    }


def build_inventory_http_evidence_chain(
    *,
    inventory_detail_baseline_payload: Any,
    inventory_detail_stockflag_payloads: Mapping[str, Any],
    inventory_detail_page_payloads: Mapping[str, Any],
    outin_baseline_payload: Any,
    outin_datetype_payloads: Mapping[str, Any],
    outin_type_payloads: Mapping[str, Any],
    outin_doctype_payloads: Mapping[str, Any],
) -> dict[str, Any]:
    inventory_detail_baseline = analyze_response_payload(inventory_detail_baseline_payload)
    outin_baseline = analyze_response_payload(outin_baseline_payload)

    stockflag_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in inventory_detail_stockflag_payloads.items()
    ]
    datetype_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in outin_datetype_payloads.items()
    ]
    type_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in outin_type_payloads.items()
    ]
    doctype_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in outin_doctype_payloads.items()
    ]

    inventory_page_probe_by_stockflag: dict[str, Any] = {}
    page_semantics_set: set[str] = set()
    for stockflag_value, page_payload in inventory_detail_page_payloads.items():
        baseline_payload = inventory_detail_stockflag_payloads.get(stockflag_value) or inventory_detail_baseline_payload
        baseline_analysis = analyze_response_payload(baseline_payload)
        page_summary = _variant_summary(value=1, payload=page_payload)
        page_semantics = classify_http_probe_semantics(
            parameter_path="page",
            baseline_analysis=baseline_analysis,
            variants=[page_summary],
        )
        inventory_page_probe_by_stockflag[str(stockflag_value)] = page_semantics
        page_semantics_set.add(page_semantics["semantics"])

    if len(page_semantics_set) == 1:
        page_semantics_value = next(iter(page_semantics_set))
    else:
        page_semantics_value = "mixed_by_scope"

    if page_semantics_value == "same_dataset":
        page_interpretation = {
            "kind": "page_ignored_in_http_or_first_page_is_full",
            "note": "纯 HTTP 下 page=0/1 在当前 stockflag 取值上都返回同一数据集，后续需决定正式抓取是固定 page=0 还是继续追查页面隐藏参数。",
        }
    elif page_semantics_value == "pagination_page_switch":
        page_interpretation = {
            "kind": "server_side_pagination",
            "note": "page 在纯 HTTP 下切换了数据子集，可作为正式分页参数继续收口终止规则。",
        }
    else:
        page_interpretation = {
            "kind": "mixed_by_scope",
            "note": "不同 stockflag 下 page 语义不一致，说明还存在范围参数与分页耦合，需继续拆解。",
        }

    inventory_detail_parameter_semantics = {
        "stockflag": classify_http_probe_semantics(
            parameter_path="stockflag",
            baseline_analysis=inventory_detail_baseline,
            variants=stockflag_variants,
        ),
        "page": {
            "parameter_path": "page",
            "semantics": page_semantics_value,
            "recommended_http_strategy": (
                "keep_current_default"
                if page_semantics_value == "same_dataset"
                else "pagination_parameter"
                if page_semantics_value == "pagination_page_switch"
                else "needs_followup"
            ),
            "mainline_ready": page_semantics_value in {"same_dataset", "pagination_page_switch"},
            "by_stockflag": inventory_page_probe_by_stockflag,
            "interpretation": page_interpretation,
        },
    }
    outin_parameter_semantics = {
        "datetype": classify_http_probe_semantics(
            parameter_path="datetype",
            baseline_analysis=outin_baseline,
            variants=datetype_variants,
        ),
        "type": classify_http_probe_semantics(
            parameter_path="type",
            baseline_analysis=outin_baseline,
            variants=type_variants,
        ),
        "doctype": classify_http_probe_semantics(
            parameter_path="doctype",
            baseline_analysis=outin_baseline,
            variants=doctype_variants,
        ),
    }

    issue_flags: list[str] = []
    if inventory_detail_parameter_semantics["stockflag"]["semantics"] != "data_subset_or_scope_switch":
        issue_flags.append("inventory_stockflag_semantics_pending")
    if inventory_detail_parameter_semantics["page"]["semantics"] not in {"same_dataset", "pagination_page_switch"}:
        issue_flags.append("inventory_pagination_semantics_pending")
    if inventory_detail_parameter_semantics["page"]["semantics"] == "same_dataset":
        issue_flags.append("inventory_page_http_same_dataset")
    if inventory_detail_parameter_semantics["page"]["semantics"] == "mixed_by_scope":
        issue_flags.append("inventory_page_semantics_mixed_by_stockflag")
    if outin_parameter_semantics["datetype"]["semantics"] != "data_subset_or_scope_switch":
        issue_flags.append("outin_datetype_semantics_pending")
    if outin_parameter_semantics["type"]["semantics"] != "data_subset_or_scope_switch":
        issue_flags.append("outin_type_semantics_pending")
    if outin_parameter_semantics["doctype"]["semantics"] != "data_subset_or_scope_switch":
        issue_flags.append("outin_doctype_semantics_pending")

    stockflag_variant_map = {str(item["value"]): item for item in stockflag_variants}
    stockflag_one_equals_two = (
        stockflag_variant_map.get("1", {}).get("row_set_signature")
        and stockflag_variant_map.get("1", {}).get("row_set_signature")
        == stockflag_variant_map.get("2", {}).get("row_set_signature")
    )

    type_sweep_summary = _signature_group_summary(type_variants)
    doctype_sweep_summary = _signature_group_summary(doctype_variants)

    return {
        "inventory_detail": {
            "endpoint": "SelDeptStockWaitList",
            "baseline": inventory_detail_baseline,
            "parameter_semantics": inventory_detail_parameter_semantics,
            "recommended_http_strategy": {
                "stockflag": (
                    "keep 0 as baseline and evaluate whether 1/2 should be admitted as separate scope variants"
                    if stockflag_one_equals_two
                    else "enumerate stockflag values and keep separate scope datasets"
                ),
                "page": "keep pagination enabled and confirm stop condition from successive page signatures",
            },
            "stockflag_equivalence": {
                "stockflag_1_equals_2": stockflag_one_equals_two,
                "baseline_row_count": inventory_detail_baseline["row_count"],
                "stockflag_0_row_count": stockflag_variant_map.get("0", {}).get("row_count"),
                "stockflag_1_row_count": stockflag_variant_map.get("1", {}).get("row_count"),
                "stockflag_2_row_count": stockflag_variant_map.get("2", {}).get("row_count"),
            },
        },
        "outin_report": {
            "endpoint": "SelOutInStockReport",
            "baseline": outin_baseline,
            "parameter_semantics": outin_parameter_semantics,
            "recommended_http_strategy": {
                "datetype": "treat as scope/date selector and keep separate request paths",
                "type": "keep current sample enum set as candidate sweep values and evaluate whether all distinct groups must be retained",
                "doctype": "use the recommended distinct values as the minimum sweep set, then validate whether equivalent groups can stay collapsed",
            },
            "type_sweep_summary": type_sweep_summary,
            "doctype_sweep_summary": doctype_sweep_summary,
        },
        "issue_flags": issue_flags,
        "conclusion": {
            "inventory_detail_mainline_ready": not {
                "inventory_stockflag_semantics_pending",
                "inventory_pagination_semantics_pending",
            }
            & set(issue_flags),
            "outin_mainline_ready": not {
                "outin_datetype_semantics_pending",
                "outin_type_semantics_pending",
                "outin_doctype_semantics_pending",
            }
            & set(issue_flags),
            "next_focus": (
                "先把库存明细统计按 stockflag=0/1 与固定 page=0 收成正式 capture 参数计划，再把 SelOutInStockReport 的 type / doctype 扩成正式 sweep 计划"
                if inventory_detail_parameter_semantics["page"]["semantics"] == "same_dataset"
                else "先解释库存明细统计 page 在页面研究与 HTTP 间的不一致，再把 SelOutInStockReport 的 type / doctype 扩成正式 sweep 计划"
            ),
        },
    }
