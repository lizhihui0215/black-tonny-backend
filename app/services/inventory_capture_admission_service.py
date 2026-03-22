from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.services.batch_service import append_capture_payload
from app.services.erp_research_service import analyze_response_payload


INVENTORY_STOCK_WAIT_LINES_ENDPOINT = "inventory_stock_wait_lines"
INVENTORY_INOUT_DOCUMENTS_ENDPOINT = "inventory_inout_documents"


def _distinct_values_from_parameter(parameter_semantics: Mapping[str, Any] | None) -> list[str]:
    variants = list((parameter_semantics or {}).get("variants") or [])
    return [str(item.get("value")) for item in variants if item.get("value") not in (None, "")]


def _outin_combo_key(datetype: str, type_value: str, doctype: str) -> str:
    return f"datetype={datetype}|type={type_value}|doctype={doctype}"


def build_outin_research_sweep_summary(
    *,
    expected_sweeps: Sequence[Mapping[str, Any]],
    sweep_payloads: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    expected_keys = {str(item["key"]) for item in expected_sweeps}
    datetype_values = sorted({str(item.get("datetype") or "") for item in expected_sweeps if item.get("datetype")})
    type_values = sorted({str(item.get("type") or "") for item in expected_sweeps if item.get("type")})
    doctype_values = sorted({str(item.get("doctype") or "") for item in expected_sweeps if item.get("doctype")})

    combo_results: list[dict[str, Any]] = []
    provided_keys: list[str] = []
    grouped_by_doctype: dict[str, list[dict[str, Any]]] = {value: [] for value in doctype_values}
    grouped_by_type: dict[str, list[dict[str, Any]]] = {value: [] for value in type_values}
    grouped_by_datetype: dict[str, list[dict[str, Any]]] = {value: [] for value in datetype_values}

    for item in sweep_payloads:
        datetype_value = str(item.get("datetype") or "")
        type_value = str(item.get("type") or "")
        doctype_value = str(item.get("doctype") or "")
        payload = item.get("payload")
        if not datetype_value or not type_value or not doctype_value or payload is None:
            raise ValueError("出入库单据 research sweep 缺少 datetype/type/doctype/payload")
        combo_key = _outin_combo_key(datetype_value, type_value, doctype_value)
        analysis = analyze_response_payload(payload)
        combo_result = {
            "key": combo_key,
            "datetype": datetype_value,
            "type": type_value,
            "doctype": doctype_value,
            "row_count": analysis["row_count"],
            "columns_signature": analysis["columns_signature"],
            "row_set_signature": analysis["row_set_signature"],
            "response_shape": analysis["response_shape"],
        }
        combo_results.append(combo_result)
        provided_keys.append(combo_key)
        grouped_by_doctype.setdefault(doctype_value, []).append(combo_result)
        grouped_by_type.setdefault(type_value, []).append(combo_result)
        grouped_by_datetype.setdefault(datetype_value, []).append(combo_result)

    missing_keys = sorted(expected_keys.difference(provided_keys))
    unexpected_keys = sorted(set(provided_keys).difference(expected_keys))

    placeholder_counter: dict[tuple[str, str, int], int] = {}
    for item in combo_results:
        placeholder_counter[
            (
                str(item["columns_signature"]),
                str(item["row_set_signature"]),
                int(item["row_count"]),
            )
        ] = placeholder_counter.get(
            (
                str(item["columns_signature"]),
                str(item["row_set_signature"]),
                int(item["row_count"]),
            ),
            0,
        ) + 1

    for item in combo_results:
        placeholder_key = (
            str(item["columns_signature"]),
            str(item["row_set_signature"]),
            int(item["row_count"]),
        )
        item["is_placeholder_like"] = int(item["row_count"]) <= 1 and placeholder_counter[placeholder_key] >= 2

    def _profile(results: Sequence[Mapping[str, Any]], expected_count: int) -> dict[str, Any]:
        column_signatures = sorted({str(item["columns_signature"]) for item in results})
        row_set_signatures = sorted({str(item["row_set_signature"]) for item in results})
        row_counts = sorted({int(item["row_count"]) for item in results})
        active_results = [item for item in results if not item.get("is_placeholder_like")]
        active_column_signatures = sorted({str(item["columns_signature"]) for item in active_results})
        return {
            "combo_count": len(results),
            "expected_combo_count": expected_count,
            "missing_combo_count": max(expected_count - len(results), 0),
            "column_signatures": column_signatures,
            "row_set_signatures": row_set_signatures,
            "row_counts": row_counts,
            "placeholder_combo_count": len(results) - len(active_results),
            "active_combo_count": len(active_results),
            "active_column_signatures": active_column_signatures,
            "schema_stable": len(column_signatures) <= 1,
            "schema_stable_after_placeholder_filter": len(active_column_signatures) <= 1,
        }

    expected_doctype_combo_count = len(datetype_values) * len(type_values)
    expected_type_combo_count = len(datetype_values) * len(doctype_values)
    expected_datetype_combo_count = len(type_values) * len(doctype_values)

    doctype_profiles = {
        value: _profile(grouped_by_doctype.get(value, []), expected_doctype_combo_count)
        for value in doctype_values
    }
    type_profiles = {
        value: _profile(grouped_by_type.get(value, []), expected_type_combo_count)
        for value in type_values
    }
    datetype_profiles = {
        value: _profile(grouped_by_datetype.get(value, []), expected_datetype_combo_count)
        for value in datetype_values
    }

    minimum_sweep_complete = not missing_keys and not unexpected_keys
    doctype_schema_stable = minimum_sweep_complete and all(
        profile["schema_stable_after_placeholder_filter"] and profile["missing_combo_count"] == 0
        for profile in doctype_profiles.values()
    )
    type_coverage_complete = minimum_sweep_complete and all(
        profile["missing_combo_count"] == 0 for profile in type_profiles.values()
    )
    datetype_coverage_complete = minimum_sweep_complete and all(
        profile["missing_combo_count"] == 0 for profile in datetype_profiles.values()
    )

    return {
        "expected_minimum_sweep_count": len(expected_keys),
        "provided_sweep_count": len(provided_keys),
        "missing_sweep_keys": missing_keys,
        "unexpected_sweep_keys": unexpected_keys,
        "minimum_sweep_complete": minimum_sweep_complete,
        "combo_results": combo_results,
        "doctype_profiles": doctype_profiles,
        "type_profiles": type_profiles,
        "datetype_profiles": datetype_profiles,
        "doctype_schema_stable": doctype_schema_stable,
        "type_coverage_complete": type_coverage_complete,
        "datetype_coverage_complete": datetype_coverage_complete,
        "placeholder_like_combo_count": sum(1 for item in combo_results if item["is_placeholder_like"]),
        "validated_datetype_values": [value for value, profile in datetype_profiles.items() if profile["missing_combo_count"] == 0],
        "validated_type_values": [value for value, profile in type_profiles.items() if profile["missing_combo_count"] == 0],
        "validated_doctype_values": [value for value, profile in doctype_profiles.items() if profile["missing_combo_count"] == 0],
        "active_doctype_values": [value for value, profile in doctype_profiles.items() if profile["active_combo_count"] > 0],
        "placeholder_only_doctype_values": [value for value, profile in doctype_profiles.items() if profile["active_combo_count"] == 0],
    }


def build_inventory_capture_admission_bundle(
    *,
    inventory_evidence: Mapping[str, Any],
    outin_research_sweep_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    inventory_detail = dict((inventory_evidence.get("inventory_detail") or {}))
    outin_report = dict((inventory_evidence.get("outin_report") or {}))

    inventory_parameter_semantics = dict((inventory_detail.get("parameter_semantics") or {}))
    outin_parameter_semantics = dict((outin_report.get("parameter_semantics") or {}))
    stockflag_equivalence = dict((inventory_detail.get("stockflag_equivalence") or {}))
    type_sweep_summary = dict((outin_report.get("type_sweep_summary") or {}))
    doctype_sweep_summary = dict((outin_report.get("doctype_sweep_summary") or {}))

    stockflag_values = _distinct_values_from_parameter(inventory_parameter_semantics.get("stockflag"))
    stockflag_equivalent_groups: list[list[str]] = []
    if stockflag_equivalence.get("stockflag_1_equals_2"):
        stockflag_equivalent_groups.append(["1", "2"])
    if stockflag_equivalent_groups:
        recommended_stockflag_values = ["0", "1"] if "0" in stockflag_values else ["1"]
    else:
        recommended_stockflag_values = stockflag_values

    page_semantics = str((inventory_parameter_semantics.get("page") or {}).get("semantics") or "")
    if page_semantics == "same_dataset":
        page_strategy = {
            "mode": "fixed_page_zero",
            "ready": True,
            "reason": "纯 HTTP 下 page=0/1 在当前 stockflag 取值上返回同一数据集，capture 正式抓取可固定 page=0。",
        }
    elif page_semantics == "pagination_page_switch":
        page_strategy = {
            "mode": "explicit_pagination",
            "ready": True,
            "reason": "纯 HTTP 下 page 切换了数据子集，capture 正式抓取应保留分页并单独收口终止条件。",
        }
    else:
        page_strategy = {
            "mode": "needs_followup",
            "ready": False,
            "reason": "page 在不同 scope 下语义不稳定，仍需继续拆解前端附加参数与页面动作链。",
        }

    inventory_blocking_issues: list[str] = []
    if str((inventory_parameter_semantics.get("stockflag") or {}).get("semantics") or "") != "data_subset_or_scope_switch":
        inventory_blocking_issues.append("stockflag 语义仍未稳定确认，暂不能作为正式 scope 参数进入 capture。")
    if not page_strategy["ready"]:
        inventory_blocking_issues.append(page_strategy["reason"])

    inventory_capture_admission_ready = not inventory_blocking_issues

    datetype_values = _distinct_values_from_parameter(outin_parameter_semantics.get("datetype"))
    type_values = [str(item) for item in (type_sweep_summary.get("recommended_distinct_values") or [])]
    doctype_values = [str(item) for item in (doctype_sweep_summary.get("recommended_distinct_values") or [])]
    doctype_equivalent_groups = [
        [str(item) for item in group]
        for group in (doctype_sweep_summary.get("equivalent_value_groups") or [])
        if group
    ]
    outin_research_sweep_summary = dict(outin_research_sweep_summary or {})
    active_doctype_values = [
        str(item)
        for item in (outin_research_sweep_summary.get("active_doctype_values") or [])
        if item not in (None, "")
    ] or doctype_values
    placeholder_only_doctype_values = [
        str(item)
        for item in (outin_research_sweep_summary.get("placeholder_only_doctype_values") or [])
        if item not in (None, "")
    ]

    outin_blocking_issues: list[str] = []
    if str((outin_parameter_semantics.get("datetype") or {}).get("semantics") or "") != "data_subset_or_scope_switch":
        outin_blocking_issues.append("datetype 语义仍未稳定确认，暂不能进入正式 capture sweep。")
    if str((outin_parameter_semantics.get("type") or {}).get("semantics") or "") != "data_subset_or_scope_switch":
        outin_blocking_issues.append("type 语义仍未稳定确认，暂不能进入正式 capture sweep。")
    doctype_semantics = str((outin_parameter_semantics.get("doctype") or {}).get("semantics") or "")
    has_outin_sweep_validation = bool(outin_research_sweep_summary)
    doctype_validation_ok = bool(outin_research_sweep_summary.get("doctype_schema_stable"))
    if doctype_semantics != "data_subset_or_scope_switch" and not doctype_validation_ok:
        outin_blocking_issues.append("doctype 语义仍未稳定确认，暂不能进入正式 capture sweep。")
    if has_outin_sweep_validation:
        if not bool(outin_research_sweep_summary.get("minimum_sweep_complete")):
            outin_blocking_issues.append("仍需验证 datetype × type × doctype 的最小组合 sweep 是否稳定覆盖单据集合。")
        elif not doctype_validation_ok:
            outin_blocking_issues.append("doctype schema 在最小 sweep 组合下仍不稳定，暂不能进入正式 capture sweep。")
    elif datetype_values and type_values and doctype_values:
        outin_blocking_issues.append(
            "仍需验证 datetype × type × doctype 的最小组合 sweep 是否稳定覆盖单据集合。"
        )

    outin_capture_admission_ready = not outin_blocking_issues
    minimum_outin_sweeps = [
        {
            "key": _outin_combo_key(datetype_value, type_value, doctype_value),
            "datetype": datetype_value,
            "type": type_value,
            "doctype": doctype_value,
        }
        for datetype_value in datetype_values
        for type_value in type_values
        for doctype_value in active_doctype_values
    ]

    return {
        "inventory_detail": {
            "capture_route_name": INVENTORY_STOCK_WAIT_LINES_ENDPOINT,
            "capture_role": "mainline_fact",
            "route_kind": "stock",
            "recommended_stockflag_values": recommended_stockflag_values,
            "stockflag_equivalent_groups": stockflag_equivalent_groups,
            "page_strategy": page_strategy,
            "capture_parameter_plan": {
                "stockflag_values": recommended_stockflag_values,
                "page_mode": page_strategy["mode"],
            },
            "capture_admission_ready": inventory_capture_admission_ready,
            "blocking_issues": inventory_blocking_issues,
        },
        "outin_report": {
            "capture_route_name": INVENTORY_INOUT_DOCUMENTS_ENDPOINT,
            "capture_role": "mainline_fact",
            "route_kind": "document",
            "recommended_datetype_values": datetype_values,
            "recommended_type_values": type_values,
            "recommended_doctype_values": active_doctype_values,
            "placeholder_only_doctype_values": placeholder_only_doctype_values,
            "doctype_equivalent_groups": doctype_equivalent_groups,
            "recommended_minimum_sweeps": minimum_outin_sweeps,
            "capture_parameter_plan": {
                "datetype_values": datetype_values,
                "type_values": type_values,
                "doctype_values": active_doctype_values,
                "validated_minimum_sweep": bool(outin_research_sweep_summary.get("minimum_sweep_complete")),
            },
            "capture_admission_ready": outin_capture_admission_ready,
            "blocking_issues": outin_blocking_issues,
            "research_sweep_summary": outin_research_sweep_summary,
        },
    }


def persist_inventory_detail_capture_admission_bundle(
    *,
    capture_batch_id: str,
    inventory_evidence: Mapping[str, Any],
    stockflag_payloads: Mapping[str, dict[str, Any] | list[Any]],
    stockflag_request_payloads: Mapping[str, dict[str, Any] | None],
    source_endpoint: str,
    account_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = build_inventory_capture_admission_bundle(inventory_evidence=inventory_evidence)
    detail_bundle = dict(bundle["inventory_detail"])
    if not detail_bundle["capture_admission_ready"]:
        raise ValueError("库存明细统计 capture 准入条件未满足: " + "；".join(detail_bundle["blocking_issues"]))

    stockflag_values = [str(item) for item in (detail_bundle.get("recommended_stockflag_values") or [])]
    missing = [value for value in stockflag_values if value not in stockflag_payloads]
    if missing:
        raise ValueError(f"缺少库存明细统计 stockflag payload: {', '.join(missing)}")

    for index, stockflag_value in enumerate(stockflag_values):
        payload = stockflag_payloads[stockflag_value]
        request_payload = stockflag_request_payloads.get(stockflag_value)
        append_capture_payload(
            capture_batch_id,
            source_endpoint=source_endpoint,
            route_kind="raw",
            payload=payload,
            request_params={
                "route_kind": "raw",
                "account_context": account_context,
                "stockflag": stockflag_value,
                "request_payload": request_payload,
            },
            page_no=index,
        )
        append_capture_payload(
            capture_batch_id,
            source_endpoint=INVENTORY_STOCK_WAIT_LINES_ENDPOINT,
            route_kind="stock",
            payload=payload,
            request_params={
                "route_kind": "stock",
                "account_context": account_context,
                "stockflag": stockflag_value,
                "request_payload": request_payload,
                "upstream_source_endpoint": source_endpoint,
                "capture_parameter_plan": detail_bundle["capture_parameter_plan"],
                "stockflag_equivalent_groups": detail_bundle["stockflag_equivalent_groups"],
                "page_strategy": detail_bundle["page_strategy"],
            },
            page_no=10 + index,
        )

    return bundle


def persist_outin_capture_research_bundle(
    *,
    capture_batch_id: str,
    inventory_evidence: Mapping[str, Any],
    sweep_payloads: Sequence[Mapping[str, Any]],
    source_endpoint: str,
    account_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    initial_bundle = build_inventory_capture_admission_bundle(inventory_evidence=inventory_evidence)
    outin_bundle = dict(initial_bundle["outin_report"])
    expected_sweeps = list(outin_bundle.get("recommended_minimum_sweeps") or [])
    sweep_summary = build_outin_research_sweep_summary(
        expected_sweeps=expected_sweeps,
        sweep_payloads=sweep_payloads,
    )
    final_bundle = build_inventory_capture_admission_bundle(
        inventory_evidence=inventory_evidence,
        outin_research_sweep_summary=sweep_summary,
    )
    _persist_outin_route_payloads(
        capture_batch_id=capture_batch_id,
        sweep_payloads=sweep_payloads,
        source_endpoint=source_endpoint,
        account_context=account_context,
        outin_bundle=final_bundle["outin_report"],
        page_offset=100,
    )
    return final_bundle


def persist_outin_capture_admission_bundle(
    *,
    capture_batch_id: str,
    inventory_evidence: Mapping[str, Any],
    outin_research_sweep_summary: Mapping[str, Any] | None = None,
    sweep_payloads: Sequence[Mapping[str, Any]],
    source_endpoint: str,
    account_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    initial_bundle = build_inventory_capture_admission_bundle(
        inventory_evidence=inventory_evidence,
        outin_research_sweep_summary=outin_research_sweep_summary,
    )
    expected_sweeps = list(initial_bundle["outin_report"].get("recommended_minimum_sweeps") or [])
    sweep_summary = build_outin_research_sweep_summary(
        expected_sweeps=expected_sweeps,
        sweep_payloads=sweep_payloads,
    )
    final_bundle = build_inventory_capture_admission_bundle(
        inventory_evidence=inventory_evidence,
        outin_research_sweep_summary=sweep_summary,
    )
    outin_bundle = dict(final_bundle["outin_report"])
    if not outin_bundle["capture_admission_ready"]:
        raise ValueError("出入库单据 capture 准入条件未满足: " + "；".join(outin_bundle["blocking_issues"]))

    expected_capture_sweeps = list(outin_bundle.get("recommended_minimum_sweeps") or [])
    expected_keys = {str(item["key"]) for item in expected_capture_sweeps}
    provided_keys = sorted(
        {
            _outin_combo_key(
                str(item.get("datetype") or ""),
                str(item.get("type") or ""),
                str(item.get("doctype") or ""),
            )
            for item in sweep_payloads
            if item.get("datetype") is not None and item.get("type") is not None and item.get("doctype") is not None
        }
        & expected_keys
    )
    missing_keys = sorted(expected_keys.difference(provided_keys))
    if missing_keys:
        raise ValueError("出入库单据 capture admission 缺少 sweep payload: " + "；".join(missing_keys))

    _persist_outin_route_payloads(
        capture_batch_id=capture_batch_id,
        sweep_payloads=sweep_payloads,
        source_endpoint=source_endpoint,
        account_context=account_context,
        outin_bundle=outin_bundle,
        page_offset=200,
        allowed_keys=expected_keys,
    )
    final_bundle["outin_report"]["capture_write_summary"] = {
        "expected_capture_sweep_count": len(expected_keys),
        "provided_capture_sweep_count": len(provided_keys),
        "missing_capture_sweep_keys": [],
        "capture_write_complete": True,
    }
    return final_bundle


def _persist_outin_route_payloads(
    *,
    capture_batch_id: str,
    sweep_payloads: Sequence[Mapping[str, Any]],
    source_endpoint: str,
    account_context: dict[str, Any] | None,
    outin_bundle: Mapping[str, Any],
    page_offset: int,
    allowed_keys: set[str] | None = None,
) -> None:
    expected_sweeps = list(outin_bundle.get("recommended_minimum_sweeps") or [])
    for index, item in enumerate(sweep_payloads):
        datetype_value = str(item.get("datetype") or "")
        type_value = str(item.get("type") or "")
        doctype_value = str(item.get("doctype") or "")
        payload = item.get("payload")
        if not datetype_value or not type_value or not doctype_value or payload is None:
            raise ValueError("出入库单据 capture sweep 缺少 datetype/type/doctype/payload")
        combo_key = _outin_combo_key(datetype_value, type_value, doctype_value)
        if allowed_keys is not None and combo_key not in allowed_keys:
            continue
        request_payload = item.get("request_payload")

        append_capture_payload(
            capture_batch_id,
            source_endpoint=source_endpoint,
            route_kind="raw",
            payload=payload,
            request_params={
                "route_kind": "raw",
                "account_context": account_context,
                "datetype": datetype_value,
                "type": type_value,
                "doctype": doctype_value,
                "combo_key": combo_key,
                "request_payload": request_payload,
            },
            page_no=index,
        )
        append_capture_payload(
            capture_batch_id,
            source_endpoint=INVENTORY_INOUT_DOCUMENTS_ENDPOINT,
            route_kind="document",
            payload=payload,
            request_params={
                "route_kind": "document",
                "account_context": account_context,
                "datetype": datetype_value,
                "type": type_value,
                "doctype": doctype_value,
                "combo_key": combo_key,
                "request_payload": request_payload,
                "upstream_source_endpoint": source_endpoint,
                "capture_parameter_plan": outin_bundle["capture_parameter_plan"],
                "doctype_equivalent_groups": outin_bundle["doctype_equivalent_groups"],
                "placeholder_only_doctype_values": outin_bundle.get("placeholder_only_doctype_values"),
                "recommended_minimum_sweeps": expected_sweeps,
                "capture_admission_ready": outin_bundle["capture_admission_ready"],
                "blocking_issues": outin_bundle["blocking_issues"],
            },
            page_no=page_offset + index,
        )
