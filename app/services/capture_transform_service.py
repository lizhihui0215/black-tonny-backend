from __future__ import annotations

import json
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import delete, insert, select

from app.core.timezone import now_local
from app.db.base import (
    capture_batches,
    capture_endpoint_payloads,
    inventory_current,
    inventory_daily_snapshot,
    sales_order_items,
    sales_orders,
)
from app.db.engine import get_capture_engine, get_serving_engine
from app.services.batch_service import update_capture_batch, upsert_analysis_batch
from app.services.summary_projection_spec import (
    SUMMARY_V0_CAPTURE_ENDPOINTS,
    SUMMARY_V0_CAPTURE_SPEC,
    canonicalize_summary_v0_row,
)


def _analysis_batch_id_for_capture(capture_batch_id: str) -> str:
    return f"analysis-{capture_batch_id}"


def _as_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    return float(value)


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _as_datetime(value: Any, fallback: datetime) -> datetime:
    if value is None or value == "":
        return fallback
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=fallback.tzinfo)
    text = str(value).strip().replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def _as_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip().split("T", 1)[0].split(" ", 1)[0]
    return date.fromisoformat(text)


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]

    if isinstance(payload, dict):
        for key in ("rows", "items", "records", "data", "payload"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return [row for row in candidate if isinstance(row, dict)]

    raise ValueError("capture payload 必须是对象数组，或包含 rows/items/records/data/payload 数组")


def _load_capture_rows(capture_batch_id: str) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    capture_engine = get_capture_engine()
    with capture_engine.begin() as connection:
        batch_row = connection.execute(
            select(capture_batches).where(capture_batches.c.capture_batch_id == capture_batch_id)
        ).mappings().first()
        if not batch_row:
            raise KeyError(f"capture batch not found: {capture_batch_id}")

        payload_rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.source_endpoint.asc(), capture_endpoint_payloads.c.page_no.asc())
        ).mappings().all()

    grouped: dict[str, list[dict[str, Any]]] = {endpoint: [] for endpoint in SUMMARY_V0_CAPTURE_ENDPOINTS}
    seen_endpoints: set[str] = set()
    for row in payload_rows:
        source_endpoint = str(row["source_endpoint"])
        if source_endpoint not in SUMMARY_V0_CAPTURE_ENDPOINTS:
            continue
        seen_endpoints.add(source_endpoint)
        grouped[source_endpoint].extend(
            [
                canonicalize_summary_v0_row(source_endpoint, record)
                for record in _extract_records(json.loads(str(row["payload_json"])))
            ]
        )

    missing_endpoints = [endpoint for endpoint in SUMMARY_V0_CAPTURE_ENDPOINTS if endpoint not in seen_endpoints]
    if missing_endpoints:
        raise ValueError(f"capture batch 缺少必要 endpoint: {', '.join(missing_endpoints)}")

    return dict(batch_row), grouped


def _validate_required_fields(endpoint: str, rows: list[dict[str, Any]]) -> None:
    required_fields = SUMMARY_V0_CAPTURE_SPEC[endpoint]["required_fields"]
    for index, row in enumerate(rows, start=1):
        missing = [field for field in required_fields if row.get(field) in (None, "")]
        if missing:
            raise ValueError(
                f"{endpoint} 第 {index} 条记录缺少必填字段: {', '.join(missing)}"
            )


def _normalize_sales_orders(
    rows: list[dict[str, Any]],
    *,
    analysis_batch_id: str,
    capture_batch_id: str,
    now: datetime,
) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        order_id = _as_string(row.get("order_id"))
        store_id = _as_string(row.get("store_id")) or "single-store"
        if not order_id:
            raise ValueError("sales_orders 记录缺少 order_id")
        normalized.append(
            {
                "analysis_batch_id": analysis_batch_id,
                "capture_batch_id": capture_batch_id,
                "store_id": store_id,
                "order_id": order_id,
                "paid_at": _as_datetime(row.get("paid_at"), now),
                "paid_amount": _as_float(row.get("paid_amount")),
                "payment_status": _as_string(row.get("payment_status")) or "paid",
                "created_at": _as_datetime(row.get("created_at"), now),
                "updated_at": _as_datetime(row.get("updated_at"), now),
            }
        )
    return normalized


def _normalize_sales_order_items(
    rows: list[dict[str, Any]],
    *,
    analysis_batch_id: str,
    capture_batch_id: str,
    now: datetime,
) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        order_id = _as_string(row.get("order_id"))
        sku_id = _as_string(row.get("sku_id"))
        if not order_id or not sku_id:
            raise ValueError("sales_order_items 记录缺少 order_id 或 sku_id")
        normalized.append(
            {
                "analysis_batch_id": analysis_batch_id,
                "capture_batch_id": capture_batch_id,
                "order_id": order_id,
                "sku_id": sku_id,
                "style_code": _as_string(row.get("style_code")),
                "color_code": _as_string(row.get("color_code")),
                "size_code": _as_string(row.get("size_code")),
                "quantity": _as_float(row.get("quantity")),
                "created_at": _as_datetime(row.get("created_at"), now),
                "updated_at": _as_datetime(row.get("updated_at"), now),
            }
        )
    return normalized


def _normalize_inventory_current(
    rows: list[dict[str, Any]],
    *,
    analysis_batch_id: str,
    capture_batch_id: str,
    now: datetime,
) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        sku_id = _as_string(row.get("sku_id"))
        store_id = _as_string(row.get("store_id")) or "single-store"
        if not sku_id:
            raise ValueError("inventory_current 记录缺少 sku_id")
        normalized.append(
            {
                "analysis_batch_id": analysis_batch_id,
                "capture_batch_id": capture_batch_id,
                "store_id": store_id,
                "sku_id": sku_id,
                "style_code": _as_string(row.get("style_code")),
                "color_code": _as_string(row.get("color_code")),
                "size_code": _as_string(row.get("size_code")),
                "on_hand_qty": _as_float(row.get("on_hand_qty")),
                "safe_stock_qty": _as_float(row.get("safe_stock_qty")),
                "season_tag": _as_string(row.get("season_tag")),
                "is_all_season": _as_bool(row.get("is_all_season"), False),
                "is_target_size": _as_bool(row.get("is_target_size"), True),
                "is_active_sale": _as_bool(row.get("is_active_sale"), True),
                "updated_at": _as_datetime(row.get("updated_at"), now),
            }
        )
    return normalized


def _normalize_inventory_daily_snapshot(
    rows: list[dict[str, Any]],
    *,
    analysis_batch_id: str,
    capture_batch_id: str,
    now: datetime,
) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        sku_id = _as_string(row.get("sku_id"))
        store_id = _as_string(row.get("store_id")) or "single-store"
        snapshot_date = row.get("snapshot_date")
        if not sku_id or snapshot_date in (None, ""):
            raise ValueError("inventory_daily_snapshot 记录缺少 sku_id 或 snapshot_date")
        normalized.append(
            {
                "analysis_batch_id": analysis_batch_id,
                "capture_batch_id": capture_batch_id,
                "snapshot_date": _as_date(snapshot_date),
                "store_id": store_id,
                "sku_id": sku_id,
                "style_code": _as_string(row.get("style_code")),
                "color_code": _as_string(row.get("color_code")),
                "size_code": _as_string(row.get("size_code")),
                "on_hand_qty": _as_float(row.get("on_hand_qty")),
                "safe_stock_qty": _as_float(row.get("safe_stock_qty")),
                "season_tag": _as_string(row.get("season_tag")),
                "is_all_season": _as_bool(row.get("is_all_season"), False),
                "is_target_size": _as_bool(row.get("is_target_size"), True),
                "is_active_sale": _as_bool(row.get("is_active_sale"), True),
                "created_at": _as_datetime(row.get("created_at"), now),
            }
        )
    return normalized


def transform_capture_batch_to_serving(
    capture_batch_id: str,
    *,
    analysis_batch_id: str | None = None,
) -> str:
    now = now_local()
    resolved_analysis_batch_id = analysis_batch_id or _analysis_batch_id_for_capture(capture_batch_id)
    batch_row, grouped_rows = _load_capture_rows(capture_batch_id)

    for endpoint, rows in grouped_rows.items():
        _validate_required_fields(endpoint, rows)

    normalized_sales_orders = _normalize_sales_orders(
        grouped_rows["sales_orders"],
        analysis_batch_id=resolved_analysis_batch_id,
        capture_batch_id=capture_batch_id,
        now=now,
    )
    normalized_sales_order_items = _normalize_sales_order_items(
        grouped_rows["sales_order_items"],
        analysis_batch_id=resolved_analysis_batch_id,
        capture_batch_id=capture_batch_id,
        now=now,
    )
    normalized_inventory_current = _normalize_inventory_current(
        grouped_rows["inventory_current"],
        analysis_batch_id=resolved_analysis_batch_id,
        capture_batch_id=capture_batch_id,
        now=now,
    )
    normalized_inventory_daily_snapshot = _normalize_inventory_daily_snapshot(
        grouped_rows["inventory_daily_snapshot"],
        analysis_batch_id=resolved_analysis_batch_id,
        capture_batch_id=capture_batch_id,
        now=now,
    )

    serving_engine = get_serving_engine()
    with serving_engine.begin() as connection:
        connection.execute(delete(sales_order_items).where(sales_order_items.c.analysis_batch_id == resolved_analysis_batch_id))
        connection.execute(delete(sales_orders).where(sales_orders.c.analysis_batch_id == resolved_analysis_batch_id))
        connection.execute(delete(inventory_current).where(inventory_current.c.analysis_batch_id == resolved_analysis_batch_id))
        connection.execute(
            delete(inventory_daily_snapshot).where(
                inventory_daily_snapshot.c.analysis_batch_id == resolved_analysis_batch_id
            )
        )

        if normalized_sales_orders:
            connection.execute(insert(sales_orders), normalized_sales_orders)
        if normalized_sales_order_items:
            connection.execute(insert(sales_order_items), normalized_sales_order_items)
        if normalized_inventory_current:
            connection.execute(insert(inventory_current), normalized_inventory_current)
        if normalized_inventory_daily_snapshot:
            connection.execute(insert(inventory_daily_snapshot), normalized_inventory_daily_snapshot)

    upsert_analysis_batch(
        resolved_analysis_batch_id,
        capture_batch_id=capture_batch_id,
        batch_status="success",
        source_endpoint="capture_transform",
        pulled_at=batch_row.get("pulled_at"),
        transformed_at=now,
    )
    update_capture_batch(
        capture_batch_id,
        batch_status="transformed",
        transformed_at=now,
    )
    return resolved_analysis_batch_id
