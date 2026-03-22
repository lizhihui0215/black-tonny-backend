from __future__ import annotations

import copy
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Callable

from app.services.erp_research_service import analyze_response_payload


RETAIL_DETAIL_CANONICAL_ENDPOINT = "sales_retail_detail_stats"


@dataclass
class RetailDetailPageResult:
    page_no: int
    page_size: int
    request_payload: dict[str, Any]
    status: int
    payload: dict[str, Any] | list[Any]
    analysis: dict[str, Any]
    stop_reason: str | None = None


@dataclass
class RetailDetailPaginationResult:
    pages: list[RetailDetailPageResult]
    stop_reason: str


def _set_payload_value(payload: dict[str, Any], path: str, value: Any) -> None:
    current = payload
    parts = path.split(".")
    for part in parts[:-1]:
        current = current.setdefault(part, {})
        if not isinstance(current, dict):
            raise TypeError(f"路径 {path} 无法写入")
    current[parts[-1]] = value


def _as_float(value: Any, default: float = 0.0) -> float:
    if value in (None, "", "null"):
        return default
    return float(value)


def _normalize_group_token(value: Any) -> str | None:
    if value in (None, "", "null"):
        return None
    text = str(value).strip()
    return text or None


def _normalize_price_token(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    return round(float(value), 2)


def _decode_unicode_escapes(value: Any) -> str:
    text = str(value or "")
    text = text.replace("%u", "\\u")
    decoded = bytes(text, "utf-8").decode("unicode_escape")
    decoded = re.sub(r"<br\s*/?>", " / ", decoded, flags=re.IGNORECASE)
    decoded = re.sub(r"\s+", " ", decoded)
    return decoded.strip()


def build_retail_detail_page_payload(
    base_payload: dict[str, Any],
    *,
    page_no: int,
    page_size: int = 20,
) -> dict[str, Any]:
    payload = copy.deepcopy(base_payload)
    _set_payload_value(payload, "page", page_no)
    _set_payload_value(payload, "pagesize", page_size)
    return payload


def fetch_retail_detail_pages(
    base_payload: dict[str, Any],
    fetch_page: Callable[[dict[str, Any]], tuple[int, dict[str, Any] | list[Any]]],
    *,
    start_page: int = 0,
    page_size: int = 20,
    max_pages: int = 200,
) -> RetailDetailPaginationResult:
    pages: list[RetailDetailPageResult] = []
    previous_signature: str | None = None

    for offset in range(max_pages):
        page_no = start_page + offset
        request_payload = build_retail_detail_page_payload(base_payload, page_no=page_no, page_size=page_size)
        status, payload = fetch_page(request_payload)
        analysis = analyze_response_payload(payload)

        stop_reason: str | None = None
        if page_no == start_page and analysis.get("row_count", 0) > page_size:
            stop_reason = "page_zero_contains_full_dataset"
        elif analysis.get("row_count", 0) == 0:
            stop_reason = "empty_page"
        elif previous_signature is not None and analysis.get("row_signature") == previous_signature:
            stop_reason = "repeated_signature"

        pages.append(
            RetailDetailPageResult(
                page_no=page_no,
                page_size=page_size,
                request_payload=request_payload,
                status=status,
                payload=payload,
                analysis=analysis,
                stop_reason=stop_reason,
            )
        )

        if stop_reason is not None:
            return RetailDetailPaginationResult(pages=pages, stop_reason=stop_reason)

        previous_signature = analysis.get("row_signature")

    return RetailDetailPaginationResult(pages=pages, stop_reason="page_limit")


def extract_retail_detail_title_map(payload: dict[str, Any] | list[Any]) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    retdata = payload.get("retdata")
    if not isinstance(retdata, list) or not retdata:
        return {}
    title_rows = retdata[0].get("Title")
    if not isinstance(title_rows, list) or not title_rows or not isinstance(title_rows[0], dict):
        return {}
    return {
        key: _decode_unicode_escapes(value)
        for key, value in title_rows[0].items()
        if key.startswith("col")
    }


def normalize_retail_detail_rows(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    retdata = payload.get("retdata")
    if not isinstance(retdata, list) or not retdata or not isinstance(retdata[0], dict):
        return []

    rows = retdata[0].get("Data")
    if not isinstance(rows, list):
        return []

    title_map = extract_retail_detail_title_map(payload)
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        size_breakdown = {
            title_map.get(key, key): _as_float(value)
            for key, value in row.items()
            if key.startswith("col")
        }
        normalized.append(
            {
                "store_name": row.get("DeptName"),
                "product_name": row.get("WareName"),
                "sku_code": row.get("Spec"),
                "color_name": row.get("ColorName"),
                "retail_price": _as_float(row.get("RetailPrice")),
                "quantity_total": _as_float(row.get("TotalNum")),
                "amount_total": _as_float(row.get("TotalMoney")),
                "retail_amount_total": _as_float(row.get("TotalRetailMoney")),
                "discount_rate": _as_float(row.get("Discount")),
                "trade_type": row.get("Trade"),
                "size_breakdown": size_breakdown,
            }
        )
    return normalized


def summarize_retail_detail_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "quantity_total": sum(_as_float(row.get("quantity_total")) for row in rows),
        "amount_total": sum(_as_float(row.get("amount_total")) for row in rows),
        "retail_amount_total": sum(_as_float(row.get("retail_amount_total")) for row in rows),
    }


def summarize_retail_detail_comparable_grain(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str | None, str | None, float | None], dict[str, float]] = {}
    for row in rows:
        key = (
            _normalize_group_token(row.get("sku_code")),
            _normalize_group_token(row.get("color_name")),
            _normalize_price_token(row.get("retail_price")),
        )
        bucket = groups.setdefault(key, {"quantity_total": 0.0, "amount_total": 0.0, "row_count": 0.0})
        bucket["quantity_total"] += _as_float(row.get("quantity_total"))
        bucket["amount_total"] += _as_float(row.get("amount_total"))
        bucket["row_count"] += 1.0

    return {
        "key_fields": ["sku_code", "color_name", "retail_price"],
        "row_count": len(groups),
        "groups": groups,
    }


def summarize_sales_list_payload(payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "line_count": 0,
            "order_count": 0,
            "quantity_total": 0.0,
            "amount_total": 0.0,
            "comparable_grain_row_count": 0,
            "comparable_grain_key_fields": [],
            "comparable_grain_groups": {},
        }
    retdata = payload.get("retdata")
    if not isinstance(retdata, dict):
        return {
            "line_count": 0,
            "order_count": 0,
            "quantity_total": 0.0,
            "amount_total": 0.0,
            "comparable_grain_row_count": 0,
            "comparable_grain_key_fields": [],
            "comparable_grain_groups": {},
        }
    columns = retdata.get("ColumnsList")
    rows = retdata.get("Data")
    if not isinstance(columns, list) or not isinstance(rows, list):
        return {
            "line_count": 0,
            "order_count": 0,
            "quantity_total": 0.0,
            "amount_total": 0.0,
            "comparable_grain_row_count": 0,
            "comparable_grain_key_fields": [],
            "comparable_grain_groups": {},
        }

    column_index = {str(column): index for index, column in enumerate(columns)}
    order_idx = column_index.get("零售单号")
    quantity_idx = column_index.get("数量")
    amount_idx = column_index.get("金额")
    store_idx = column_index.get("店铺名称")
    style_idx = column_index.get("款号")
    color_idx = column_index.get("颜色")
    tag_price_idx = column_index.get("吊牌价")

    order_ids: set[str] = set()
    quantity_total = 0.0
    amount_total = 0.0
    comparable_groups: dict[tuple[str | None, str | None, float | None], dict[str, float]] = {}
    for row in rows:
        if not isinstance(row, list):
            continue
        if order_idx is not None and order_idx < len(row) and row[order_idx] not in (None, ""):
            order_ids.add(str(row[order_idx]))
        if quantity_idx is not None and quantity_idx < len(row):
            quantity_total += _as_float(row[quantity_idx])
        if amount_idx is not None and amount_idx < len(row):
            amount_total += _as_float(row[amount_idx])
        group_key = (
            _normalize_group_token(row[style_idx]) if style_idx is not None and style_idx < len(row) else None,
            _normalize_group_token(row[color_idx]) if color_idx is not None and color_idx < len(row) else None,
            _normalize_price_token(row[tag_price_idx]) if tag_price_idx is not None and tag_price_idx < len(row) else None,
        )
        if any(part is not None for part in group_key):
            bucket = comparable_groups.setdefault(group_key, {"quantity_total": 0.0, "amount_total": 0.0, "line_count": 0.0})
            bucket["quantity_total"] += _as_float(row[quantity_idx]) if quantity_idx is not None and quantity_idx < len(row) else 0.0
            bucket["amount_total"] += _as_float(row[amount_idx]) if amount_idx is not None and amount_idx < len(row) else 0.0
            bucket["line_count"] += 1.0

    return {
        "line_count": len(rows),
        "order_count": len(order_ids),
        "quantity_total": quantity_total,
        "amount_total": amount_total,
        "comparable_grain_row_count": len(comparable_groups),
        "comparable_grain_key_fields": ["style_code", "color", "tag_price"],
        "comparable_grain_groups": comparable_groups,
    }


def _build_metric_status(retail_value: float | None, sales_value: float | None) -> tuple[str, float | None, float | None]:
    if retail_value is None or sales_value is None:
        return "差异待解释", None, None

    diff = retail_value - sales_value
    diff_rate = None if sales_value == 0 else diff / sales_value
    if diff == 0:
        return "一致", diff, diff_rate

    tolerance = max(1.0, abs(sales_value) * 0.01)
    if abs(diff) <= tolerance:
        return "可接受差异", diff, diff_rate
    return "差异待解释", diff, diff_rate


def build_sales_retail_grain_alignment(
    *,
    retail_rows: list[dict[str, Any]],
    sales_summary: dict[str, Any],
) -> dict[str, Any]:
    retail_grain = summarize_retail_detail_comparable_grain(retail_rows)
    sales_groups = sales_summary.get("comparable_grain_groups") or {}
    retail_groups = retail_grain.get("groups") or {}

    sales_keys = set(sales_groups.keys())
    retail_keys = set(retail_groups.keys())
    overlap_keys = sales_keys & retail_keys
    sales_only_keys = sorted(sales_keys - retail_keys)
    retail_only_keys = sorted(retail_keys - sales_keys)

    quantity_mismatch_count = 0
    amount_mismatch_count = 0
    for key in overlap_keys:
        sales_bucket = sales_groups[key]
        retail_bucket = retail_groups[key]
        if round(float(sales_bucket["quantity_total"]), 6) != round(float(retail_bucket["quantity_total"]), 6):
            quantity_mismatch_count += 1
        if round(float(sales_bucket["amount_total"]), 2) != round(float(retail_bucket["amount_total"]), 2):
            amount_mismatch_count += 1

    def _serialize_key(key: tuple[str | None, str | None, float | None]) -> dict[str, Any]:
        return {
            "style_code": key[0],
            "color": key[1],
            "tag_price": key[2],
        }

    return {
        "comparable": True,
        "key_fields": retail_grain["key_fields"],
        "retail_row_count": retail_grain["row_count"],
        "sales_aggregated_row_count": len(sales_keys),
        "overlap_row_count": len(overlap_keys),
        "sales_only_row_count": len(sales_only_keys),
        "retail_only_row_count": len(retail_only_keys),
        "quantity_mismatch_count": quantity_mismatch_count,
        "amount_mismatch_count": amount_mismatch_count,
        "sales_only_samples": [_serialize_key(key) for key in sales_only_keys[:5]],
        "retail_only_samples": [_serialize_key(key) for key in retail_only_keys[:5]],
    }


def build_sales_reconciliation_report(
    *,
    retail_pages: RetailDetailPaginationResult,
    sales_list_payload: dict[str, Any] | list[Any],
    retail_request_payload: dict[str, Any],
    sales_request_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    retail_rows: list[dict[str, Any]] = []
    for page in retail_pages.pages:
        retail_rows.extend(normalize_retail_detail_rows(page.payload))

    retail_summary = summarize_retail_detail_rows(retail_rows)
    sales_summary = summarize_sales_list_payload(sales_list_payload)
    grain_alignment = build_sales_retail_grain_alignment(
        retail_rows=retail_rows,
        sales_summary=sales_summary,
    )
    sales_summary_output = {key: value for key, value in sales_summary.items() if key != "comparable_grain_groups"}

    row_status, row_diff, row_diff_rate = _build_metric_status(
        float(retail_summary["row_count"]),
        float(sales_summary["comparable_grain_row_count"]),
    )
    qty_status, qty_diff, qty_diff_rate = _build_metric_status(
        retail_summary["quantity_total"],
        sales_summary["quantity_total"],
    )
    amount_status, amount_diff, amount_diff_rate = _build_metric_status(
        retail_summary["amount_total"],
        sales_summary["amount_total"],
    )

    return {
        "retail_detail_source_endpoint": RETAIL_DETAIL_CANONICAL_ENDPOINT,
        "sales_list_source_endpoint": "yeusoft.report.sales_list",
        "retail_detail_request_payload": retail_request_payload,
        "sales_list_request_payload": sales_request_payload,
        "retail_detail": {
            "page_count": len(retail_pages.pages),
            "stop_reason": retail_pages.stop_reason,
            "summary": retail_summary,
        },
        "sales_list": {
            "summary": sales_summary_output,
        },
        "grain_alignment": grain_alignment,
        "metrics": [
            {
                "metric": "line_count",
                "label": "零售宽表行数 vs 销售清单按店铺/款号/颜色/吊牌价聚合后行数",
                "retail_detail_value": retail_summary["row_count"],
                "sales_list_value": sales_summary["comparable_grain_row_count"],
                "diff": row_diff,
                "diff_rate": row_diff_rate,
                "status": row_status,
            },
            {
                "metric": "quantity_total",
                "label": "销售件数",
                "retail_detail_value": retail_summary["quantity_total"],
                "sales_list_value": sales_summary["quantity_total"],
                "diff": qty_diff,
                "diff_rate": qty_diff_rate,
                "status": qty_status,
            },
            {
                "metric": "amount_total",
                "label": "销售金额",
                "retail_detail_value": retail_summary["amount_total"],
                "sales_list_value": sales_summary["amount_total"],
                "diff": amount_diff,
                "diff_rate": amount_diff_rate,
                "status": amount_status,
            },
            {
                "metric": "sales_list_order_count",
                "label": "销售清单订单数（零售明细统计当前无单据号）",
                "retail_detail_value": None,
                "sales_list_value": sales_summary["order_count"],
                "diff": None,
                "diff_rate": None,
                "status": "不同粒度，不直接对账",
            },
        ],
    }


def serialize_retail_detail_pagination_result(result: RetailDetailPaginationResult) -> dict[str, Any]:
    return {
        "stop_reason": result.stop_reason,
        "pages": [
            {
                **asdict(page),
                "payload": page.payload,
            }
            for page in result.pages
        ],
    }
