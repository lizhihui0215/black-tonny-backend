from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from app.services.erp_research_service import analyze_response_payload

RETURN_DETAIL_FILTER_TITLE_TO_PAYLOAD_KEY = {
    "品牌": "TrademarkCode",
    "年份": "Years",
    "季节": "Season",
    "大类": "TypeCode",
    "中类": "TypeCode",
    "小类": "TypeCode",
    "波段": "State",
    "主题": "Style",
    "上架模式": "PlatId",
    "订单来源": "Order",
    "提货方式": "ArriveStore",
}


def _variant_summary(*, value: Any, payload: Any) -> dict[str, Any]:
    analysis = analyze_response_payload(payload)
    return {
        "value": str(value),
        "row_count": analysis["row_count"],
        "columns_signature": analysis["columns_signature"],
        "row_set_signature": analysis["row_set_signature"],
        "response_shape": analysis["response_shape"],
        "error_code": analysis.get("error_code"),
        "error_message": analysis.get("error_message"),
    }


def _summarize_filter_dimensions(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    retdata = payload.get("retdata")
    if not isinstance(retdata, list) or not retdata:
        return []
    rows = retdata[0].get("Data") if isinstance(retdata[0], Mapping) else []
    if not isinstance(rows, list):
        return []
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        options = row.get("List") or []
        option_codes = [
            str(item.get("Code"))
            for item in options
            if isinstance(item, Mapping) and item.get("Code") not in (None, "")
        ]
        result.append(
            {
                "title": str(row.get("TitleName") or ""),
                "field": str(row.get("Field") or ""),
                "option_count": len(option_codes),
                "sample_option_codes": option_codes[:8],
            }
        )
    return result


def _summarize_filter_mapping_coverage(payload: Any) -> dict[str, Any]:
    dimensions = _summarize_filter_dimensions(payload)
    visible_titles = [str(item.get("title") or "") for item in dimensions if str(item.get("title") or "")]
    mapped_titles = [title for title in visible_titles if title in RETURN_DETAIL_FILTER_TITLE_TO_PAYLOAD_KEY]
    unmapped_titles = [title for title in visible_titles if title not in RETURN_DETAIL_FILTER_TITLE_TO_PAYLOAD_KEY]
    return {
        "visible_titles": visible_titles,
        "mapped_titles": mapped_titles,
        "unmapped_titles": unmapped_titles,
        "mapping_complete": not unmapped_titles,
    }


def build_return_detail_base_info_filter_probes(base_info_payload: Any) -> dict[str, dict[str, Any]]:
    probes: dict[str, dict[str, Any]] = {}
    first_values_by_title: dict[str, tuple[str, str]] = {}

    for row in _summarize_filter_dimensions(base_info_payload):
        title = str(row.get("title") or "")
        payload_key = RETURN_DETAIL_FILTER_TITLE_TO_PAYLOAD_KEY.get(title)
        sample_codes = row.get("sample_option_codes") or []
        if not payload_key or not sample_codes:
            continue
        code = str(sample_codes[0])
        first_values_by_title[title] = (payload_key, code)
        probes[f"{title}({payload_key})={code}"] = {payload_key: code}

    full_type = first_values_by_title.get("小类")
    if full_type:
        type_payload_key, type_code = full_type
        for title in ("品牌", "年份", "季节", "波段", "上架模式", "订单来源", "提货方式"):
            pair = first_values_by_title.get(title)
            if not pair:
                continue
            payload_key, code = pair
            probes[f"小类({type_payload_key})={type_code},{title}({payload_key})={code}"] = {
                type_payload_key: type_code,
                payload_key: code,
            }

    return probes


def build_return_detail_http_evidence_chain(
    *,
    base_info_payload: Any,
    baseline_payload: Any,
    type_payloads: Mapping[str, Any],
    narrow_filter_payloads: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    baseline = analyze_response_payload(baseline_payload)
    type_variants = [_variant_summary(value=value, payload=payload) for value, payload in type_payloads.items()]
    narrow_filter_variants = [
        _variant_summary(value=value, payload=payload)
        for value, payload in (narrow_filter_payloads or {}).items()
    ]

    successful_variants = [item for item in type_variants if not item.get("error_code")]
    error_variants = [item for item in type_variants if item.get("error_code")]
    successful_narrow_filters = [item for item in narrow_filter_variants if not item.get("error_code")]
    error_groups: dict[str, list[str]] = defaultdict(list)
    for item in error_variants:
        error_groups[str(item.get("error_code") or "unknown")].append(str(item["value"]))
    narrow_error_groups: dict[str, list[str]] = defaultdict(list)
    for item in narrow_filter_variants:
        if item.get("error_code"):
            narrow_error_groups[str(item.get("error_code") or "unknown")].append(str(item["value"]))

    if successful_variants and error_variants:
        type_semantics = "partial_availability_by_type"
        recommended_http_strategy = "type_seed_sweep"
    elif successful_variants:
        distinct_row_sets = {item.get("row_set_signature") for item in successful_variants}
        type_semantics = "data_subset_or_scope_switch" if len(distinct_row_sets) > 1 else "same_dataset"
        recommended_http_strategy = "type_seed_sweep" if len(distinct_row_sets) > 1 else "single_request"
    else:
        type_semantics = "all_seed_values_error"
        recommended_http_strategy = "needs_followup"

    blocking_issues: list[str] = []
    if not successful_variants:
        blocking_issues.append("当前 seed type 值全部触发服务端错误")
    if any(item.get("error_code") == "4000" for item in error_variants):
        blocking_issues.append("服务端 SQL 截断错误仍未解除")
    if not successful_variants:
        blocking_issues.append("尚未确认可稳定返回数据的 type 取值")
    if narrow_filter_variants and not successful_narrow_filters:
        blocking_issues.append("已验证的窄过滤 seed 仍全部触发服务端错误")

    capture_parameter_plan = {
        "baseline_payload": {
            "menuid": "E004003004",
            "gridid": "E004003004_2",
            "warecause": "",
            "spenum": "",
        },
        "type_seed_values": [item["value"] for item in type_variants],
        "successful_type_values": [item["value"] for item in successful_variants],
        "narrow_filter_seed_values": [item["value"] for item in narrow_filter_variants],
        "page_mode": "not_applicable_yet",
    }

    return {
        "return_detail": {
            "endpoint": "SelReturnStockList",
            "base_info_endpoint": "ReturnStockBaseInfo",
            "base_info_filter_dimensions": _summarize_filter_dimensions(base_info_payload),
            "base_info_filter_coverage": _summarize_filter_mapping_coverage(base_info_payload),
            "baseline": baseline,
            "type_probe_summary": {
                "tested_values": [item["value"] for item in type_variants],
                "successful_values": [item["value"] for item in successful_variants],
                "error_values": [item["value"] for item in error_variants],
                "error_groups": dict(error_groups),
                "variants": type_variants,
            },
            "narrow_filter_probe_summary": {
                "tested_values": [item["value"] for item in narrow_filter_variants],
                "successful_values": [item["value"] for item in successful_narrow_filters],
                "error_values": [item["value"] for item in narrow_filter_variants if item.get("error_code")],
                "error_groups": dict(narrow_error_groups),
                "variants": narrow_filter_variants,
            },
            "parameter_semantics": {
                "type": {
                    "parameter_path": "type",
                    "semantics": type_semantics,
                    "recommended_http_strategy": recommended_http_strategy,
                    "variants": type_variants,
                }
            },
            "recommended_http_strategy": {
                "baseline": "先固定 menuid/gridid 与空 warecause/spenum，并优先验证省略 type 与 blank type 是否就是页面默认查询窗口",
                "type": "先做受控 type sweep；若仍全部报错，再补页面附加参数或更窄过滤条件",
                "narrow_filters": "优先验证品牌/年份/季节/上架模式/订单来源/提货方式等窄过滤是否能绕过服务端 SQL 截断",
            },
            "capture_admission_ready": False,
            "capture_parameter_plan": capture_parameter_plan,
            "blocking_issues": blocking_issues,
            "judgment": (
                "真实接口已通过 HTTP 回证，但当前 seed type 集仍全部触发服务端错误"
                if not successful_variants
                else "真实接口已通过 HTTP 回证，当前可继续按 type 拆分范围并评估 capture 准入"
            ),
        },
        "issue_flags": [
            *(["return_detail_all_seed_types_error"] if not successful_variants else []),
            *(["return_detail_sql_truncation"] if any(item.get("error_code") == "4000" for item in error_variants) else []),
            *(["return_detail_narrow_filters_still_error"] if narrow_filter_variants and not successful_narrow_filters else []),
        ],
        "conclusion": {
            "return_detail_mainline_ready": False,
            "next_focus": (
                "页面默认 payload、type seed 和已验证窄过滤仍全部报错；下一步应优先定位页面动作链或服务端字段边界，而不是继续盲加基础过滤"
                if not successful_variants
                else "对成功的 type 值继续补单变量与分页验证，再评估 capture 准入"
            ),
        },
    }
