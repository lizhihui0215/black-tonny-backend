from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any


DATE_FIELD_HINTS = {
    "bdate",
    "edate",
    "begindate",
    "enddate",
    "salebdate",
    "saleedate",
    "birthbdate",
    "birthedate",
    "lastdate",
    "ybegindate",
    "yenddate",
    "mbegindate",
    "menddate",
    "date1",
}

ORG_FIELD_HINTS = {
    "depart",
    "depts",
    "warecause",
    "wareclause",
    "operater",
    "spenum",
    "volumenumber",
}

SEARCH_FIELD_HINTS = {
    "search",
    "searchtype",
    "condition",
    "searchval",
    "name",
    "tag",
}

ENUM_FIELD_HINTS = {
    "rtype",
    "type",
    "datetype",
    "stockflag",
    "doctype",
    "tiem",
    "sort",
}

PAGINATION_FIELD_HINTS = {
    "page",
    "pagesize",
    "pageindex",
    "pagesize",
}

DIY_CONTEXT_HINTS = {
    "menuid",
    "gridid",
}

COST_FIELD_PATTERN = re.compile(r"(成本|cost)", re.IGNORECASE)
PRICE_FIELD_PATTERN = re.compile(r"(吊牌|零售|售价|牌价|RetailPrice|TagPrice|Price)", re.IGNORECASE)
DEFAULT_FIRST_PAGE_SIZE_PROBE_CANDIDATES = (20, 100, 1000, 10000, 0)
SALES_HEADER_TOKEN_HINTS = {
    "sale_no",
    "sale_date",
    "operator",
    "sales_qty",
    "sales_amount",
    "received_amount",
    "tag_amount",
    "discount",
}
SALES_DETAIL_TOKEN_HINTS = {
    "sale_no",
    "detail_serial",
    "style_code",
    "product_name",
    "tag_price",
    "unit_price",
    "color",
    "size",
    "quantity",
    "sales_amount",
    "tag_amount",
}
SALES_FIELD_ALIASES = {
    "salenum": "sale_no",
    "销售单号": "sale_no",
    "零售单号": "sale_no",
    "saledate": "sale_date",
    "销售日期": "sale_date",
    "operman": "operator",
    "导购员": "operator",
    "vipcardid": "vip_card_no",
    "会员卡号": "vip_card_no",
    "totalsaleamount": "sales_qty",
    "销量": "sales_qty",
    "totalsaleretailmoney": "tag_amount",
    "totalsaleretailmoeny": "tag_amount",
    "吊牌额": "tag_amount",
    "吊牌金额": "tag_amount",
    "totalsalemoney": "sales_amount",
    "销售金额": "sales_amount",
    "金额": "sales_amount",
    "receivemoney": "received_amount",
    "实收金额": "received_amount",
    "discount": "discount",
    "折扣": "discount",
    "款号": "style_code",
    "品名": "product_name",
    "吊牌价": "tag_price",
    "单价": "unit_price",
    "颜色": "color",
    "尺码": "size",
    "数量": "quantity",
    "明细流水": "detail_serial",
    "店铺名称": "store_name",
    "店铺": "store_name",
}
DEFAULT_SALES_JOIN_KEYS = (
    "sale_no",
    "sale_date",
    "operator",
    "vip_card_no",
)


@dataclass(frozen=True)
class EnumProbeSpec:
    path: str
    candidates: tuple[Any, ...]


@dataclass(frozen=True)
class PaginationProbeSpec:
    page_path: str
    page_size_path: str
    start_page: int = 0
    paged_size: int = 20
    include_zero_size_probe: bool = False
    first_page_probe_sizes: tuple[int, ...] = DEFAULT_FIRST_PAGE_SIZE_PROBE_CANDIDATES


@dataclass(frozen=True)
class ExplorationStrategy:
    title: str
    pagination: PaginationProbeSpec | None = None
    enum_probes: tuple[EnumProbeSpec, ...] = ()
    context_fields: tuple[str, ...] = ()
    combine_enum_with_pagination: bool = False
    result_snapshot: bool = False


EXPLORATION_TARGETS: dict[str, tuple[str, ...]] = {
    "sales_inventory": (
        "销售清单",
        "零售明细统计",
        "库存明细统计",
        "出入库单据",
    )
}

EXPLORATION_STRATEGIES: dict[str, ExplorationStrategy] = {
    "零售明细统计": ExplorationStrategy(
        title="零售明细统计",
        pagination=PaginationProbeSpec(
            page_path="page",
            page_size_path="pagesize",
            start_page=0,
            paged_size=20,
            include_zero_size_probe=True,
        ),
    ),
    "销售清单": ExplorationStrategy(
        title="销售清单",
        enum_probes=(
            EnumProbeSpec(
                path="parameter.Tiem",
                candidates=("0", "1", "2"),
            ),
        ),
        context_fields=("parameter.Depart",),
    ),
    "库存明细统计": ExplorationStrategy(
        title="库存明细统计",
        pagination=PaginationProbeSpec(
            page_path="page",
            page_size_path="pagesize",
            start_page=0,
            paged_size=20,
        ),
        enum_probes=(
            EnumProbeSpec(
                path="stockflag",
                candidates=("0", "1", "2"),
            ),
        ),
        combine_enum_with_pagination=True,
    ),
    "出入库单据": ExplorationStrategy(
        title="出入库单据",
        pagination=PaginationProbeSpec(
            page_path="page",
            page_size_path="pagesize",
            start_page=0,
            paged_size=20,
            include_zero_size_probe=True,
        ),
        enum_probes=(
            EnumProbeSpec(
                path="datetype",
                candidates=("1", "2"),
            ),
        ),
        context_fields=("type", "doctype"),
        combine_enum_with_pagination=True,
    ),
}


def slugify(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", value, flags=re.UNICODE)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "report"


def parse_data_raw(block: str) -> dict[str, Any] | list[Any] | str:
    match = re.search(r"--data-raw\s+(\$?)(['\"])(.*)\2", block, re.DOTALL)
    if not match:
        return {}
    raw = match.group(3).strip()
    if match.group(1) == "$":
        raw = bytes(raw, "utf-8").decode("unicode_escape")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def parse_report_specs(doc_path: Path) -> list[dict[str, Any]]:
    text = doc_path.read_text("utf-8")
    pattern = re.compile(r"^###\s+(.+?)\n+```bash\n(.*?)```", re.MULTILINE | re.DOTALL)
    specs: list[dict[str, Any]] = []
    for title, block in pattern.findall(text):
        if title in {"CompanyUserPassWord", "Login"}:
            continue
        url_match = re.search(r"curl\s+'([^']+)'", block)
        if not url_match:
            continue
        specs.append(
            {
                "title": title.strip(),
                "url": url_match.group(1).strip(),
                "payload": parse_data_raw(block),
                "filename": f"{slugify(title)}.json",
            }
        )
    return specs


def flatten_payload(payload: Any, prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(flatten_payload(value, next_prefix))
        return flattened
    if isinstance(payload, list):
        flattened[prefix] = payload
        return flattened
    flattened[prefix] = payload
    return flattened


def _leaf_name(path: str) -> str:
    return path.split(".")[-1].lower()


def classify_filter_fields(payload: Any) -> dict[str, list[dict[str, Any]]]:
    flat = flatten_payload(payload)
    categories = {
        "date_fields": [],
        "organization_fields": [],
        "search_fields": [],
        "enum_fields": [],
        "pagination_fields": [],
        "diy_context_fields": [],
        "other_fields": [],
    }
    for path, value in flat.items():
        if not path:
            continue
        leaf = _leaf_name(path)
        item = {"path": path, "value": value}
        if leaf in DATE_FIELD_HINTS:
            categories["date_fields"].append(item)
        elif leaf in ORG_FIELD_HINTS:
            categories["organization_fields"].append(item)
        elif leaf in SEARCH_FIELD_HINTS:
            categories["search_fields"].append(item)
        elif leaf in ENUM_FIELD_HINTS or (isinstance(value, str) and "," in value):
            categories["enum_fields"].append(item)
        elif leaf in PAGINATION_FIELD_HINTS:
            categories["pagination_fields"].append(item)
        elif leaf in DIY_CONTEXT_HINTS or path.startswith("parameter."):
            categories["diy_context_fields"].append(item)
        else:
            categories["other_fields"].append(item)
    return categories


def infer_auth_mode(url: str) -> str:
    return "Authorization" if "/JyApi/" in url else "token"


def infer_domain(title: str) -> str:
    if any(key in title for key in ("销售", "零售", "商品")):
        return "sales"
    if any(key in title for key in ("库存", "进销存", "出入库")):
        return "inventory"
    if "会员" in title:
        return "member"
    if "储值" in title:
        return "stored_value"
    if any(key in title for key in ("流水", "月报", "单据")):
        return "payment_and_docs"
    return "unknown"


def infer_risk_labels(filter_fields: dict[str, list[dict[str, Any]]], title: str) -> list[str]:
    risks: list[str] = []
    if filter_fields["pagination_fields"]:
        risks.append("需要翻页")
    if filter_fields["enum_fields"]:
        risks.append("需要扫枚举")
    if filter_fields["diy_context_fields"]:
        risks.append("DIY 报表隐藏条件")
    if any(key in title for key in ("分析", "排行", "月报")):
        risks.append("结果视图重叠风险")
    return risks


def infer_capture_strategy(risk_labels: Sequence[str], title: str) -> str:
    if "结果视图重叠风险" in risk_labels and any(key in title for key in ("分析", "排行", "月报")):
        return "结果快照"
    if "需要扫枚举" in risk_labels:
        return "枚举 sweep"
    if "需要翻页" in risk_labels:
        return "自动翻页"
    return "单请求"


def infer_source_kind(title: str) -> str:
    if any(key in title for key in ("清单", "明细", "单据", "中心")):
        return "源接口候选"
    if any(key in title for key in ("分析", "排行", "月报", "统计")):
        return "结果快照候选"
    return "待判断"


def _is_placeholder_mapping_row(row: Any) -> bool:
    if not isinstance(row, Mapping):
        return False
    if not row:
        return True
    return all(value in (None, "", "null") for value in row.values())


def _extract_table_data(payload: Any) -> tuple[list[str], list[Any], str]:
    if isinstance(payload, Mapping) and isinstance(payload.get("retdata"), Mapping):
        retdata = payload["retdata"]
        if isinstance(retdata.get("ColumnsList"), list) and isinstance(retdata.get("Data"), list):
            return list(retdata["ColumnsList"]), list(retdata["Data"]), "retdata.ColumnsList+Data"
        if isinstance(retdata.get("Data"), list):
            rows = list(retdata["Data"])
            if str(retdata.get("DataCount") or retdata.get("Count") or "").strip() == "0" and all(
                _is_placeholder_mapping_row(row) for row in rows
            ):
                rows = []
            columns = list(rows[0].keys()) if rows and isinstance(rows[0], Mapping) else []
            return columns, rows, "retdata.Data"

    if isinstance(payload, Mapping) and isinstance(payload.get("retdata"), list):
        for item in payload["retdata"]:
            if isinstance(item, Mapping) and isinstance(item.get("ColumnsList"), list) and isinstance(item.get("Data"), list):
                return list(item["ColumnsList"]), list(item["Data"]), "retdata[].ColumnsList+Data"
            if isinstance(item, Mapping) and isinstance(item.get("Title"), list) and isinstance(item.get("Data"), list):
                rows = list(item["Data"])
                columns = list(rows[0].keys()) if rows and isinstance(rows[0], Mapping) else []
                return columns, rows, "retdata[].Title+Data"
            if isinstance(item, Mapping) and isinstance(item.get("Data"), list):
                rows = list(item["Data"])
                if str(item.get("DataCount") or item.get("Count") or "").strip() == "0" and all(
                    _is_placeholder_mapping_row(row) for row in rows
                ):
                    rows = []
                columns = list(rows[0].keys()) if rows and isinstance(rows[0], Mapping) else []
                return columns, rows, "retdata[].Data"

    if isinstance(payload, Mapping) and isinstance(payload.get("Data"), Mapping):
        data = payload["Data"]
        if isinstance(data.get("Columns"), list) and isinstance(data.get("List"), list):
            return list(data["Columns"]), list(data["List"]), "Data.Columns+List"

    if isinstance(payload, Mapping) and isinstance(payload.get("PageData"), Mapping):
        page_data = payload["PageData"]
        if isinstance(page_data.get("Items"), list):
            rows = list(page_data["Items"])
            columns = list(rows[0].keys()) if rows and isinstance(rows[0], Mapping) else []
            return columns, rows, "PageData.Items"

    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if isinstance(value, list) and value:
                if isinstance(value[0], Mapping):
                    return list(value[0].keys()), list(value), f"{key}[]"
                if isinstance(value[0], list):
                    return [], list(value), f"{key}[[]]"

    return [], [], "unknown"


def _field_stats(columns: list[str], rows: list[Any]) -> dict[str, Any]:
    cost_fields: list[dict[str, Any]] = []
    price_fields: list[dict[str, Any]] = []

    if columns and rows and isinstance(rows[0], list):
        for index, column in enumerate(columns):
            values = [row[index] if index < len(row) else None for row in rows]
            stat = {
                "field": column,
                "non_null_count": sum(1 for value in values if value not in (None, "", "null")),
            }
            if COST_FIELD_PATTERN.search(column):
                cost_fields.append(stat)
            if PRICE_FIELD_PATTERN.search(column):
                price_fields.append(stat)
        return {
            "cost_fields": cost_fields,
            "price_fields": price_fields,
        }

    if rows and isinstance(rows[0], Mapping):
        keys = columns or list(rows[0].keys())
        for key in keys:
            values = [row.get(key) for row in rows if isinstance(row, Mapping)]
            stat = {
                "field": key,
                "non_null_count": sum(1 for value in values if value not in (None, "", "null")),
            }
            if COST_FIELD_PATTERN.search(key):
                cost_fields.append(stat)
            if PRICE_FIELD_PATTERN.search(key):
                price_fields.append(stat)
        return {
            "cost_fields": cost_fields,
            "price_fields": price_fields,
        }

    return {
        "cost_fields": [],
        "price_fields": [],
    }


def _build_row_signature(rows: list[Any], limit: int = 5) -> str:
    preview = rows[:limit]
    raw = json.dumps(preview, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    digest = hashlib.sha1(f"{len(rows)}|{raw}".encode("utf-8")).hexdigest()
    return digest[:16]


def _normalize_row_for_set_signature(row: Any, columns: list[str]) -> Any:
    if isinstance(row, Mapping):
        return row
    if isinstance(row, list) and columns:
        return {
            column: row[index] if index < len(row) else None
            for index, column in enumerate(columns)
        }
    return row


def _build_row_set_signature(columns: list[str], rows: list[Any]) -> str:
    normalized_rows = [
        json.dumps(
            _normalize_row_for_set_signature(row, columns),
            ensure_ascii=False,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )
        for row in rows
    ]
    normalized_rows.sort()
    digest = hashlib.sha1(
        json.dumps(normalized_rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return digest[:16]


def _build_columns_signature(columns: list[str]) -> str:
    digest = hashlib.sha1(
        json.dumps(columns, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return digest[:16]


def normalize_sales_field_token(value: str) -> str:
    compact = re.sub(r"[\s_\-]+", "", str(value)).strip()
    lowered = compact.lower()
    if lowered in SALES_FIELD_ALIASES:
        return SALES_FIELD_ALIASES[lowered]
    if compact in SALES_FIELD_ALIASES:
        return SALES_FIELD_ALIASES[compact]
    return lowered or compact


def _collect_sales_tokens(values: Sequence[str]) -> list[str]:
    tokens = {
        normalize_sales_field_token(value)
        for value in values
        if str(value).strip()
    }
    return sorted(token for token in tokens if token)


def analyze_response_payload(payload: Any, *, sample_path: str | None = None) -> dict[str, Any]:
    error_code = None
    error_message = None
    if isinstance(payload, Mapping) and isinstance(payload.get("raw_text"), str):
        return analyze_response_payload(payload["raw_text"], sample_path=sample_path)
    if isinstance(payload, str):
        stripped = payload.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return analyze_response_payload(json.loads(stripped), sample_path=sample_path)
            except Exception:
                errcode_match = re.search(r'"errcode"\s*:\s*"([^"]*)"', stripped)
                errmsg_match = re.search(r'"errmsg"\s*:\s*"([^"]*)"', stripped)
                if errcode_match:
                    error_code = errcode_match.group(1)
                if errmsg_match:
                    error_message = errmsg_match.group(1)
    columns, rows, shape = _extract_table_data(payload)
    field_stats = _field_stats(columns, rows)
    if isinstance(payload, Mapping):
        error_code = payload.get("errcode") or payload.get("error_code") or payload.get("code")
        error_message = payload.get("errmsg") or payload.get("error_message") or payload.get("message")
    result = {
        "response_shape": shape,
        "row_count": len(rows),
        "column_count": len(columns),
        "columns": columns,
        "columns_preview": columns[:20],
        "columns_signature": _build_columns_signature(columns),
        "row_signature": _build_row_signature(rows),
        "row_set_signature": _build_row_set_signature(columns, rows),
        "normalized_tokens": _collect_sales_tokens(columns),
        "cost_fields": field_stats["cost_fields"],
        "price_fields": field_stats["price_fields"],
        "error_code": error_code,
        "error_message": error_message,
    }
    if sample_path is not None:
        result["sample_path"] = sample_path
    return result


def extract_normalized_table_rows(payload: Any) -> list[dict[str, Any]]:
    columns, rows, _ = _extract_table_data(payload)
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, Mapping):
            normalized_rows.append(
                {
                    normalize_sales_field_token(str(key)): value
                    for key, value in row.items()
                    if normalize_sales_field_token(str(key))
                }
            )
            continue
        if isinstance(row, list) and columns:
            normalized_rows.append(
                {
                    normalize_sales_field_token(str(column)): (row[index] if index < len(row) else None)
                    for index, column in enumerate(columns)
                    if normalize_sales_field_token(str(column))
                }
            )
    return normalized_rows


def _normalize_join_value(value: Any) -> str | None:
    if value in (None, "", "null"):
        return None
    text = str(value).strip()
    return text or None


def _field_ownership(rows: Sequence[Mapping[str, Any]]) -> set[str]:
    fields: set[str] = set()
    for row in rows:
        fields.update(key for key in row.keys() if key)
    return fields


def build_sales_head_line_join_analysis(
    *,
    document_payload: Any,
    detail_payload: Any,
    candidate_keys: Sequence[str] = DEFAULT_SALES_JOIN_KEYS,
) -> dict[str, Any]:
    document_rows = extract_normalized_table_rows(document_payload)
    detail_rows = extract_normalized_table_rows(detail_payload)

    document_fields = _field_ownership(document_rows)
    detail_fields = _field_ownership(detail_rows)
    common_fields = sorted(document_fields & detail_fields)

    per_key: list[dict[str, Any]] = []
    stable_join_candidates: list[str] = []

    for key in candidate_keys:
        document_values = [_normalize_join_value(row.get(key)) for row in document_rows]
        detail_values = [_normalize_join_value(row.get(key)) for row in detail_rows]
        document_non_empty = [value for value in document_values if value is not None]
        detail_non_empty = [value for value in detail_values if value is not None]
        document_unique = set(document_non_empty)
        detail_unique = set(detail_non_empty)
        overlap = document_unique & detail_unique

        detail_counts: dict[str, int] = {}
        for value in detail_non_empty:
            detail_counts[value] = detail_counts.get(value, 0) + 1

        matched_detail_counts = [detail_counts[value] for value in sorted(overlap) if value in detail_counts]
        document_rows_with_match = sum(1 for value in document_non_empty if value in overlap)
        document_rows_without_match = len(document_non_empty) - document_rows_with_match
        relationship = "insufficient_evidence"
        if matched_detail_counts:
            if max(matched_detail_counts) > 1:
                relationship = "one_to_many"
            else:
                relationship = "one_to_one"

        document_overlap_rate = (
            len(overlap) / len(document_unique) if document_unique else None
        )
        detail_overlap_rate = (
            len(overlap) / len(detail_unique) if detail_unique else None
        )

        stable_candidate = (
            len(overlap) > 0
            and document_overlap_rate is not None
            and document_overlap_rate >= 0.9
            and relationship in {"one_to_many", "one_to_one"}
        )
        if stable_candidate:
            stable_join_candidates.append(key)

        per_key.append(
            {
                "key": key,
                "document_non_empty_count": len(document_non_empty),
                "detail_non_empty_count": len(detail_non_empty),
                "document_unique_count": len(document_unique),
                "detail_unique_count": len(detail_unique),
                "overlap_unique_count": len(overlap),
                "document_overlap_rate": document_overlap_rate,
                "detail_overlap_rate": detail_overlap_rate,
                "relationship": relationship,
                "document_rows_with_match": document_rows_with_match,
                "document_rows_without_match": document_rows_without_match,
                "matched_detail_rows_per_document": {
                    "min": min(matched_detail_counts) if matched_detail_counts else None,
                    "max": max(matched_detail_counts) if matched_detail_counts else None,
                    "avg": (
                        sum(matched_detail_counts) / len(matched_detail_counts)
                        if matched_detail_counts
                        else None
                    ),
                },
                "stable_candidate": stable_candidate,
            }
        )

    return {
        "document_row_count": len(document_rows),
        "detail_row_count": len(detail_rows),
        "field_ownership": {
            "document_only": sorted(document_fields - detail_fields),
            "common": common_fields,
            "detail_only": sorted(detail_fields - document_fields),
        },
        "candidate_keys": per_key,
        "stable_join_candidates": stable_join_candidates,
        "sale_no_head_line_link_stable": "sale_no" in stable_join_candidates,
    }


def classify_http_probe_semantics(
    *,
    parameter_path: str,
    baseline_analysis: Mapping[str, Any] | None,
    variants: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    leaf = _leaf_name(parameter_path)
    normalized_variants = [
        {
            "value": item.get("value"),
            "row_count": item.get("row_count"),
            "columns_signature": item.get("columns_signature"),
            "row_set_signature": item.get("row_set_signature") or item.get("row_signature"),
            "response_shape": item.get("response_shape"),
        }
        for item in variants
        if item
    ]
    baseline_signature = (
        baseline_analysis.get("row_set_signature") or baseline_analysis.get("row_signature")
        if baseline_analysis
        else None
    )
    baseline_columns = baseline_analysis.get("columns_signature") if baseline_analysis else None

    semantics = "insufficient_evidence"
    if normalized_variants and baseline_analysis:
        variant_signatures = {item["row_set_signature"] for item in normalized_variants}
        variant_columns = {item["columns_signature"] for item in normalized_variants}
        same_as_baseline = all(
            item["row_set_signature"] == baseline_signature and item["columns_signature"] == baseline_columns
            for item in normalized_variants
        )
        if parameter_path == "grain_route" and len(variant_signatures) > 1:
            semantics = "multi_grain_route"
        elif same_as_baseline:
            semantics = "same_dataset"
        elif len(variant_columns) > 1 or any(item["columns_signature"] != baseline_columns for item in normalized_variants):
            semantics = "mixed"
        elif leaf in PAGINATION_FIELD_HINTS:
            semantics = "pagination_page_switch"
        elif leaf in DATE_FIELD_HINTS or leaf in ORG_FIELD_HINTS:
            semantics = "scope_or_date_boundary"
        elif leaf in ENUM_FIELD_HINTS:
            semantics = "data_subset_or_scope_switch"
        else:
            semantics = "data_subset_or_scope_switch"

    if semantics == "same_dataset":
        recommended_http_strategy = "keep_current_default"
        mainline_ready = True
    elif semantics == "scope_or_date_boundary":
        recommended_http_strategy = "date_or_scope_parameter"
        mainline_ready = True
    elif semantics == "pagination_page_switch":
        recommended_http_strategy = "pagination_parameter"
        mainline_ready = True
    elif semantics == "data_subset_or_scope_switch":
        recommended_http_strategy = "enum_or_scope_sweep"
        mainline_ready = False
    elif semantics == "multi_grain_route":
        recommended_http_strategy = "split_head_and_line_routes"
        mainline_ready = True
    else:
        recommended_http_strategy = "needs_followup"
        mainline_ready = False

    return {
        "parameter_path": parameter_path,
        "semantics": semantics,
        "recommended_http_strategy": recommended_http_strategy,
        "mainline_ready": mainline_ready,
        "baseline": {
            "row_count": baseline_analysis.get("row_count") if baseline_analysis else None,
            "columns_signature": baseline_columns,
            "row_set_signature": baseline_signature,
        },
        "variants": normalized_variants,
    }


def analyze_grid_view_payload(payload: Any, *, sample_path: str | None = None) -> dict[str, Any]:
    data_items = payload.get("Data") if isinstance(payload, Mapping) else None
    if not isinstance(data_items, list) or not data_items:
        raise ValueError("当前 payload 不符合 GetViewGridList 响应结构")

    item = data_items[0]
    if not isinstance(item, Mapping):
        raise ValueError("当前 payload 缺少 Data[0] 字段")

    view_list = item.get("ViewList")
    if not isinstance(view_list, list):
        raise ValueError("当前 payload 缺少 ViewList 字段")

    columns = [
        {
            "code": row.get("GCode"),
            "name": row.get("GName"),
            "sort": row.get("GSort"),
            "is_sum": row.get("GIsSum"),
            "is_filter": row.get("GIsFilter"),
            "is_order": row.get("GIsOrder"),
        }
        for row in view_list
        if isinstance(row, Mapping)
    ]
    column_codes = [str(column["code"]) for column in columns if column.get("code")]
    column_names = [str(column["name"]) for column in columns if column.get("name")]
    result = {
        "response_shape": "Data[].ViewList",
        "grid_id": item.get("GridID"),
        "view_id": item.get("ViewID"),
        "view_name": item.get("ViewName"),
        "column_count": len(columns),
        "columns": columns,
        "column_codes": column_codes,
        "column_names": column_names,
        "column_codes_preview": column_codes[:20],
        "column_names_preview": column_names[:20],
        "columns_signature": _build_columns_signature(column_codes),
        "normalized_tokens": _collect_sales_tokens([*column_codes, *column_names]),
    }
    if sample_path is not None:
        result["sample_path"] = sample_path
    return result


def _infer_sales_grain_kind(
    *,
    variant_type: str,
    grid_id: str | None,
    normalized_tokens: Sequence[str],
) -> tuple[str, str]:
    token_set = set(normalized_tokens)
    header_score = len(token_set & SALES_HEADER_TOKEN_HINTS)
    detail_score = len(token_set & SALES_DETAIL_TOKEN_HINTS)
    explicit_detail_tokens = token_set & {
        "detail_serial",
        "style_code",
        "product_name",
        "tag_price",
        "unit_price",
        "color",
        "size",
        "quantity",
    }

    if variant_type == "grid_schema" and grid_id and str(grid_id).endswith("_1"):
        return "document_header_schema", "gridid=_1 且字段集合以单据汇总字段为主"
    if variant_type == "grid_schema" and grid_id and str(grid_id).endswith("_2"):
        return "line_detail_schema", "gridid=_2 且字段集合包含款号/颜色/尺码/数量等明细字段"
    if len(explicit_detail_tokens) >= 3 and detail_score >= 4:
        return "line_detail_candidate", "字段集合包含款号/颜色/尺码/数量/金额等明细特征"
    if header_score >= 4 and len(explicit_detail_tokens) <= 1:
        return "document_header_candidate", "字段集合以销售单号/销售日期/金额/实收等单据汇总字段为主"
    return "unknown", "字段特征不足，暂不能稳定判断粒度"


def _summarize_token_overlap(left: Sequence[str], right: Sequence[str]) -> dict[str, list[str]]:
    left_set = set(left)
    right_set = set(right)
    return {
        "common": sorted(left_set & right_set),
        "left_only": sorted(left_set - right_set),
        "right_only": sorted(right_set - left_set),
    }


def build_sales_menu_grain_analysis(
    *,
    menuid: str,
    document_grid_payload: Any,
    detail_grid_payload: Any,
    document_data_payload: Any,
    detail_data_payload: Any,
) -> dict[str, Any]:
    document_grid = analyze_grid_view_payload(document_grid_payload)
    detail_grid = analyze_grid_view_payload(detail_grid_payload)
    document_data = analyze_response_payload(document_data_payload)
    detail_data = analyze_response_payload(detail_data_payload)

    document_grid_kind, document_grid_reason = _infer_sales_grain_kind(
        variant_type="grid_schema",
        grid_id=document_grid.get("grid_id"),
        normalized_tokens=document_grid.get("normalized_tokens") or [],
    )
    detail_grid_kind, detail_grid_reason = _infer_sales_grain_kind(
        variant_type="grid_schema",
        grid_id=detail_grid.get("grid_id"),
        normalized_tokens=detail_grid.get("normalized_tokens") or [],
    )
    document_data_kind, document_data_reason = _infer_sales_grain_kind(
        variant_type="data",
        grid_id=None,
        normalized_tokens=document_data.get("normalized_tokens") or [],
    )
    detail_data_kind, detail_data_reason = _infer_sales_grain_kind(
        variant_type="data",
        grid_id=None,
        normalized_tokens=detail_data.get("normalized_tokens") or [],
    )

    document_schema_vs_data = _summarize_token_overlap(
        document_grid.get("normalized_tokens") or [],
        document_data.get("normalized_tokens") or [],
    )
    detail_schema_vs_data = _summarize_token_overlap(
        detail_grid.get("normalized_tokens") or [],
        detail_data.get("normalized_tokens") or [],
    )
    header_vs_detail = _summarize_token_overlap(
        document_data.get("normalized_tokens") or [],
        detail_data.get("normalized_tokens") or [],
    )

    candidate_join_keys = [
        token
        for token in header_vs_detail["common"]
        if token in {"sale_no", "sale_date", "operator", "store_name", "vip_card_no"}
    ]
    head_line_link_feasible = "sale_no" in candidate_join_keys

    supporting_signals = [
        f"_1 grid 列数 {document_grid['column_count']}，_2 grid 列数 {detail_grid['column_count']}",
        f"SelSaleReport 行数 {document_data['row_count']}，销售清单当前样本行数 {detail_data['row_count']}",
        f"_1 与 SelSaleReport 共同字段 {', '.join(document_schema_vs_data['common'][:8]) or '无'}",
        f"_2 与销售清单共同字段 {', '.join(detail_schema_vs_data['common'][:8]) or '无'}",
    ]

    return {
        "menuid": menuid,
        "variants": {
            "document_grid": {
                **document_grid,
                "grain_kind": document_grid_kind,
                "grain_reason": document_grid_reason,
            },
            "detail_grid": {
                **detail_grid,
                "grain_kind": detail_grid_kind,
                "grain_reason": detail_grid_reason,
            },
            "document_data": {
                **document_data,
                "grain_kind": document_data_kind,
                "grain_reason": document_data_reason,
            },
            "detail_data": {
                **detail_data,
                "grain_kind": detail_data_kind,
                "grain_reason": detail_data_reason,
            },
        },
        "overlap": {
            "document_schema_vs_data": document_schema_vs_data,
            "detail_schema_vs_data": detail_schema_vs_data,
            "document_vs_detail_data": header_vs_detail,
            "candidate_join_keys": candidate_join_keys,
        },
        "conclusion": {
            "document_variant_kind": document_data_kind,
            "detail_variant_kind": detail_data_kind,
            "head_line_link_feasible": head_line_link_feasible,
            "supporting_signals": supporting_signals,
        },
    }


def analyze_response_sample(sample_path: Path) -> dict[str, Any]:
    payload = json.loads(sample_path.read_text("utf-8"))
    return analyze_response_payload(payload, sample_path=str(sample_path))


def find_latest_sample(raw_root: Path, title: str) -> Path | None:
    target_name = f"{title}.json"
    candidates = sorted(raw_root.glob(f"*/{target_name}"))
    return candidates[-1] if candidates else None


def build_report_matrix(report_doc_path: Path, raw_root: Path) -> list[dict[str, Any]]:
    matrix: list[dict[str, Any]] = []
    for spec in parse_report_specs(report_doc_path):
        filter_fields = classify_filter_fields(spec["payload"])
        risk_labels = infer_risk_labels(filter_fields, spec["title"])
        sample_path = find_latest_sample(raw_root, spec["title"])
        sample_analysis = analyze_response_sample(sample_path) if sample_path else None
        matrix.append(
            {
                "title": spec["title"],
                "domain": infer_domain(spec["title"]),
                "url": spec["url"],
                "auth_mode": infer_auth_mode(spec["url"]),
                "source_kind": infer_source_kind(spec["title"]),
                "capture_strategy": infer_capture_strategy(risk_labels, spec["title"]),
                "risk_labels": risk_labels,
                "filter_fields": filter_fields,
                "sample_analysis": sample_analysis,
            }
        )
    return matrix


def get_exploration_target_titles(target: str) -> tuple[str, ...]:
    if target not in EXPLORATION_TARGETS:
        raise KeyError(target)
    return EXPLORATION_TARGETS[target]


def get_exploration_strategy(title: str) -> ExplorationStrategy | None:
    return EXPLORATION_STRATEGIES.get(title)


def should_persist_capture(mode: str, *, skip_db: bool, persist_detection: bool) -> bool:
    if skip_db:
        return False
    if mode == "explore":
        return persist_detection
    return True


def _get_payload_value(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _set_payload_value(payload: Any, path: str, value: Any) -> None:
    current = payload
    parts = path.split(".")
    for part in parts[:-1]:
        if not isinstance(current, dict):
            raise TypeError(f"路径 {path} 无法写入")
        current = current.setdefault(part, {})
    if not isinstance(current, dict):
        raise TypeError(f"路径 {path} 无法写入")
    current[parts[-1]] = value


def set_nested_payload_value(payload: Any, path: str, value: Any) -> None:
    _set_payload_value(payload, path, value)


def _dedupe_candidates(sample_value: Any, candidates: Sequence[Any], limit: int) -> list[Any]:
    result: list[Any] = []
    for candidate in (sample_value, *candidates):
        if candidate in result or candidate is None:
            continue
        result.append(candidate)
        if len(result) >= limit:
            break
    return result


def resolve_first_page_probe_sizes(
    base_candidates: Sequence[int] | None = None,
    edge_candidates: Sequence[int] = (),
) -> tuple[int, ...]:
    ordered: list[int] = []
    source_candidates = (
        DEFAULT_FIRST_PAGE_SIZE_PROBE_CANDIDATES
        if base_candidates is None
        else base_candidates
    )
    for raw in [*source_candidates, *edge_candidates]:
        try:
            candidate = int(raw)
        except (TypeError, ValueError):
            continue
        if candidate < 0 or candidate in ordered:
            continue
        ordered.append(candidate)
    return tuple(ordered)


def _json_signature(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_exploration_cases(
    report_spec: Mapping[str, Any],
    strategy: ExplorationStrategy,
    *,
    max_pages: int,
    enum_limit: int,
    edge_page_sizes: Sequence[int] = (),
) -> list[dict[str, Any]]:
    base_payload = copy.deepcopy(report_spec["payload"])
    if not isinstance(base_payload, dict):
        raise TypeError("当前探索模式只支持 JSON object payload")

    cases: list[dict[str, Any]] = []
    seen_signatures: set[tuple[str, str]] = set()

    def add_case(kind: str, payload: dict[str, Any], label_parts: list[str], probe_context: dict[str, Any]) -> None:
        signature = _json_signature(payload)
        dedupe_key = (kind, signature)
        if dedupe_key in seen_signatures:
            return
        seen_signatures.add(dedupe_key)
        case_id = slugify("__".join([strategy.title, kind, *label_parts]))
        cases.append(
            {
                "case_id": case_id,
                "kind": kind,
                "label": " | ".join(label_parts) if label_parts else "base",
                "payload": payload,
                "probe_context": probe_context,
            }
        )

    add_case("base", copy.deepcopy(base_payload), [], {"context_fields": list(strategy.context_fields)})

    enum_variants = [({"payload": copy.deepcopy(base_payload), "labels": [], "context": {}})]
    if strategy.enum_probes:
        enum_variants = []
        candidate_lists: list[tuple[EnumProbeSpec, list[Any]]] = []
        for enum_probe in strategy.enum_probes:
            sample_value = _get_payload_value(base_payload, enum_probe.path)
            candidates = _dedupe_candidates(sample_value, enum_probe.candidates, enum_limit)
            candidate_lists.append((enum_probe, candidates))

        for combination in product(*[candidates for _, candidates in candidate_lists]):
            payload = copy.deepcopy(base_payload)
            labels: list[str] = []
            context: dict[str, Any] = {}
            for (enum_probe, _), candidate in zip(candidate_lists, combination):
                _set_payload_value(payload, enum_probe.path, candidate)
                labels.append(f"{enum_probe.path}={candidate}")
                context[enum_probe.path] = candidate
            enum_variants.append({"payload": payload, "labels": labels, "context": context})

        if not strategy.combine_enum_with_pagination:
            for variant in enum_variants:
                add_case("enum", variant["payload"], variant["labels"], variant["context"])

    pagination = strategy.pagination
    if pagination:
        first_page_probe_sizes = resolve_first_page_probe_sizes(
            pagination.first_page_probe_sizes,
            edge_page_sizes,
        )
        for page_size in first_page_probe_sizes:
            payload = copy.deepcopy(base_payload)
            _set_payload_value(payload, pagination.page_path, pagination.start_page)
            _set_payload_value(payload, pagination.page_size_path, page_size)
            add_case(
                "page_size_probe",
                payload,
                [f"{pagination.page_path}={pagination.start_page}", f"{pagination.page_size_path}={page_size}"],
                {
                    pagination.page_path: pagination.start_page,
                    pagination.page_size_path: page_size,
                    "probe_type": "first_page_size",
                },
            )

        variants = enum_variants if strategy.combine_enum_with_pagination else [{"payload": copy.deepcopy(base_payload), "labels": [], "context": {}}]
        for variant in variants:
            if pagination.include_zero_size_probe:
                payload = copy.deepcopy(variant["payload"])
                _set_payload_value(payload, pagination.page_path, pagination.start_page)
                _set_payload_value(payload, pagination.page_size_path, 0)
                add_case(
                    "pagination",
                    payload,
                    [*variant["labels"], f"{pagination.page_path}={pagination.start_page}", f"{pagination.page_size_path}=0"],
                    {
                        **variant["context"],
                        pagination.page_path: pagination.start_page,
                        pagination.page_size_path: 0,
                    },
                )

            for offset in range(max_pages):
                page_value = pagination.start_page + offset
                payload = copy.deepcopy(variant["payload"])
                _set_payload_value(payload, pagination.page_path, page_value)
                _set_payload_value(payload, pagination.page_size_path, pagination.paged_size)
                add_case(
                    "pagination",
                    payload,
                    [
                        *variant["labels"],
                        f"{pagination.page_path}={page_value}",
                        f"{pagination.page_size_path}={pagination.paged_size}",
                    ],
                    {
                        **variant["context"],
                        pagination.page_path: page_value,
                        pagination.page_size_path: pagination.paged_size,
                    },
                )

    return cases


def build_first_page_size_probe_cases(
    report_spec: Mapping[str, Any],
    strategy: ExplorationStrategy,
    *,
    probe_sizes: Sequence[int],
) -> list[dict[str, Any]]:
    pagination = strategy.pagination
    if pagination is None:
        return []

    base_payload = copy.deepcopy(report_spec["payload"])
    if not isinstance(base_payload, dict):
        raise TypeError("当前探索模式只支持 JSON object payload")

    cases: list[dict[str, Any]] = []
    seen_page_sizes: set[int] = set()
    for page_size in resolve_first_page_probe_sizes((), probe_sizes):
        if page_size in seen_page_sizes:
            continue
        seen_page_sizes.add(page_size)
        payload = copy.deepcopy(base_payload)
        _set_payload_value(payload, pagination.page_path, pagination.start_page)
        _set_payload_value(payload, pagination.page_size_path, page_size)
        case_id = slugify(
            "__".join(
                [
                    strategy.title,
                    "page_size_probe",
                    f"{pagination.page_path}={pagination.start_page}",
                    f"{pagination.page_size_path}={page_size}",
                ]
            )
        )
        cases.append(
            {
                "case_id": case_id,
                "kind": "page_size_probe",
                "label": f"{pagination.page_path}={pagination.start_page} | {pagination.page_size_path}={page_size}",
                "payload": payload,
                "probe_context": {
                    pagination.page_path: pagination.start_page,
                    pagination.page_size_path: page_size,
                    "probe_type": "first_page_size",
                },
            }
        )
    return cases


def should_trigger_edge_page_probe(
    first_page_size_probe: Mapping[str, Any],
    *,
    threshold: int = 10000,
) -> bool:
    for entry in first_page_size_probe.get("tested_page_sizes") or []:
        page_size = entry.get("page_size")
        row_count = entry.get("row_count")
        if page_size in (0, threshold) and isinstance(row_count, int) and row_count >= threshold:
            return True
    return False


def _summarize_first_page_size_probe(
    strategy: ExplorationStrategy,
    probe_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    pagination = strategy.pagination
    if pagination is None:
        return {
            "supported": False,
            "reason": "no_pagination_fields",
            "tested_page_sizes": [],
            "first_page_contains_full_dataset": None,
            "recommended_first_page_size": None,
            "large_page_supported": False,
            "large_page_ignored": False,
        }

    candidate_order = list(resolve_first_page_probe_sizes(pagination.first_page_probe_sizes))
    page_size_results: dict[int, dict[str, Any]] = {}
    for result in probe_results:
        if result.get("kind") != "page_size_probe":
            continue
        context = result.get("probe_context") or {}
        if context.get(pagination.page_path) != pagination.start_page:
            continue
        page_size = context.get(pagination.page_size_path)
        if not isinstance(page_size, int):
            continue
        analysis = result.get("analysis") or {}
        page_size_results[page_size] = {
            "page_size": page_size,
            "status": result.get("status"),
            "row_count": analysis.get("row_count"),
            "column_count": analysis.get("column_count"),
            "row_signature": analysis.get("row_signature"),
            "row_set_signature": analysis.get("row_set_signature"),
            "response_shape": analysis.get("response_shape"),
            "error": result.get("error"),
            "usable": bool(analysis) and analysis.get("row_count", 0) >= 0,
        }

    tested_page_sizes: list[dict[str, Any]] = []
    for page_size in candidate_order:
        if page_size in page_size_results:
            tested_page_sizes.append(page_size_results[page_size])

    if not tested_page_sizes:
        return {
            "supported": True,
            "reason": "no_successful_probe_results",
            "tested_page_sizes": [],
            "first_page_contains_full_dataset": None,
            "recommended_first_page_size": None,
            "large_page_supported": False,
            "large_page_ignored": False,
        }

    baseline = page_size_results.get(pagination.paged_size)
    successful_entries = [
        entry
        for entry in tested_page_sizes
        if entry.get("status") is not None and (entry.get("row_set_signature") or entry.get("row_signature"))
    ]

    first_page_contains_full_dataset = False
    recommended_first_page_size = pagination.paged_size if baseline else None
    large_page_supported = False
    large_page_ignored = False

    if baseline and baseline.get("row_count") is not None:
        baseline_row_count = int(baseline["row_count"])
        baseline_signature = baseline.get("row_signature")
        baseline_row_set_signature = baseline.get("row_set_signature") or baseline_signature

        if baseline_row_count > pagination.paged_size:
            first_page_contains_full_dataset = True

        larger_successes = [
            entry
            for entry in successful_entries
            if isinstance(entry["page_size"], int) and entry["page_size"] > pagination.paged_size
        ]
        zero_probe = page_size_results.get(0)

        if larger_successes and all(
            (entry.get("row_set_signature") or entry.get("row_signature")) == baseline_row_set_signature
            for entry in larger_successes
        ):
            first_page_contains_full_dataset = True
            large_page_ignored = True

        if zero_probe and (zero_probe.get("row_set_signature") or zero_probe.get("row_signature")) == baseline_row_set_signature:
            first_page_contains_full_dataset = True

        better_entries = [
            entry
            for entry in successful_entries
            if entry["page_size"] != pagination.paged_size
            and isinstance(entry.get("row_count"), int)
            and int(entry["row_count"]) > baseline_row_count
        ]

        stable_better_by_signature: dict[str, list[dict[str, Any]]] = {}
        for entry in better_entries:
            signature = entry.get("row_set_signature") or entry.get("row_signature")
            if not signature:
                continue
            stable_better_by_signature.setdefault(signature, []).append(entry)

        stable_better_candidates: list[dict[str, Any]] = []
        for signature, entries in stable_better_by_signature.items():
            matching_zero_probe = zero_probe and (
                (zero_probe.get("row_set_signature") or zero_probe.get("row_signature")) == signature
            )
            if len(entries) >= 2 or matching_zero_probe:
                stable_better_candidates.extend(entries)

        if stable_better_candidates:
            best_row_count = max(int(entry["row_count"]) for entry in stable_better_candidates)
            ranked_candidates = [
                entry for entry in stable_better_candidates if int(entry["row_count"]) == best_row_count
            ]
            ranked_candidates.sort(
                key=lambda entry: (
                    entry["page_size"] == 0,
                    int(entry["page_size"]),
                )
            )
            recommended_first_page_size = int(ranked_candidates[0]["page_size"])
            large_page_supported = True

    return {
        "supported": True,
        "reason": None,
        "tested_page_sizes": tested_page_sizes,
        "first_page_contains_full_dataset": first_page_contains_full_dataset,
        "recommended_first_page_size": recommended_first_page_size,
        "large_page_supported": large_page_supported,
        "large_page_ignored": large_page_ignored,
    }


def _summarize_enum_probe_semantics(
    strategy: ExplorationStrategy,
    probe_results: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if not strategy.enum_probes:
        return []

    results: list[dict[str, Any]] = []
    for enum_probe in strategy.enum_probes:
        observed: list[dict[str, Any]] = []
        for result in probe_results:
            analysis = result.get("analysis") or {}
            if not analysis or analysis.get("row_count", 0) <= 0:
                continue
            context = result.get("probe_context") or {}
            if enum_probe.path not in context:
                continue
            if strategy.pagination:
                page_value = context.get(strategy.pagination.page_path)
                page_size = context.get(strategy.pagination.page_size_path)
                if page_value != strategy.pagination.start_page:
                    continue
                if page_size not in (None, strategy.pagination.paged_size, 0):
                    continue
            observed.append(
                {
                    "value": context.get(enum_probe.path),
                    "row_count": analysis.get("row_count"),
                    "column_count": analysis.get("column_count"),
                    "columns_signature": analysis.get("columns_signature"),
                    "row_set_signature": analysis.get("row_set_signature") or analysis.get("row_signature"),
                    "response_shape": analysis.get("response_shape"),
                }
            )

        deduped_by_value: dict[Any, dict[str, Any]] = {}
        for item in observed:
            deduped_by_value.setdefault(item["value"], item)
        variants = list(deduped_by_value.values())

        if len(variants) < 2:
            results.append(
                {
                    "path": enum_probe.path,
                    "classification": "insufficient_evidence",
                    "distinct_value_count": len(variants),
                    "variants": variants,
                }
            )
            continue

        row_set_count = len({variant["row_set_signature"] for variant in variants})
        columns_count = len({variant["columns_signature"] for variant in variants})

        if row_set_count == 1 and columns_count == 1:
            classification = "same_dataset"
        elif row_set_count > 1 and columns_count == 1:
            classification = "data_subset_or_scope_switch"
        elif row_set_count == 1 and columns_count > 1:
            classification = "view_switch"
        else:
            classification = "mixed"

        results.append(
            {
                "path": enum_probe.path,
                "classification": classification,
                "distinct_value_count": len(variants),
                "distinct_row_set_count": row_set_count,
                "distinct_columns_count": columns_count,
                "variants": variants,
            }
        )

    return results


def summarize_exploration_results(
    strategy: ExplorationStrategy,
    probe_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    found_additional_pages = False
    enum_paths = tuple(enum_probe.path for enum_probe in strategy.enum_probes)
    risk_labels: list[str] = []

    def result_signature(result: Mapping[str, Any]) -> tuple[Any, ...]:
        analysis = result.get("analysis") or {}
        return (
            analysis.get("response_shape"),
            analysis.get("row_count"),
            analysis.get("column_count"),
            analysis.get("row_set_signature") or analysis.get("row_signature"),
            analysis.get("row_signature"),
        )

    def enum_scope_key(context: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
        return tuple((path, context.get(path)) for path in enum_paths if path in context)

    def is_usable_result(result: Mapping[str, Any]) -> bool:
        analysis = result.get("analysis") or {}
        return bool(analysis) and analysis.get("row_count", 0) > 0

    pagination_baselines: dict[tuple[tuple[str, Any], ...], tuple[Any, ...]] = {}
    if strategy.pagination:
        for result in probe_results:
            if not is_usable_result(result):
                continue
            context = result.get("probe_context") or {}
            if context.get(strategy.pagination.page_path) != strategy.pagination.start_page:
                continue
            page_size = context.get(strategy.pagination.page_size_path)
            if page_size not in (None, strategy.pagination.paged_size):
                continue
            pagination_baselines.setdefault(enum_scope_key(context), result_signature(result))

        for result in probe_results:
            if not is_usable_result(result):
                continue
            context = result.get("probe_context") or {}
            page_value = context.get(strategy.pagination.page_path)
            if not isinstance(page_value, int) or page_value <= strategy.pagination.start_page:
                continue
            baseline = pagination_baselines.get(enum_scope_key(context))
            if baseline is not None and result_signature(result) != baseline:
                found_additional_pages = True
                break

    enum_signatures_by_scope: dict[tuple[tuple[str, Any], ...], tuple[Any, ...]] = {}
    if enum_paths:
        for result in probe_results:
            if not is_usable_result(result):
                continue
            context = result.get("probe_context") or {}
            scope_key = enum_scope_key(context)
            if not scope_key:
                continue
            if strategy.pagination:
                page_value = context.get(strategy.pagination.page_path)
                page_size = context.get(strategy.pagination.page_size_path)
                if page_value != strategy.pagination.start_page:
                    continue
                if page_size not in (None, strategy.pagination.paged_size):
                    continue
            enum_signatures_by_scope.setdefault(scope_key, result_signature(result))

    found_distinct_enum_results = len(set(enum_signatures_by_scope.values())) > 1

    if strategy.result_snapshot:
        risk_labels.append("结果视图重叠风险")
        recommended = "结果快照"
    else:
        if found_distinct_enum_results:
            risk_labels.append("需要扫枚举")
        if found_additional_pages:
            risk_labels.append("需要翻页")

        if found_distinct_enum_results:
            recommended = "枚举 sweep"
        elif found_additional_pages:
            recommended = "自动翻页"
        else:
            recommended = "单请求"

    return {
        "found_additional_pages": found_additional_pages,
        "found_distinct_enum_results": found_distinct_enum_results,
        "risk_labels": risk_labels,
        "recommended_capture_strategy": recommended,
        "first_page_size_probe": _summarize_first_page_size_probe(strategy, probe_results),
        "enum_probe_semantics": _summarize_enum_probe_semantics(strategy, probe_results),
    }
