from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select

from app.db.base import (
    analysis_batches,
    inventory_current,
    inventory_daily_snapshot,
    sales_order_items,
    sales_orders,
)
from app.db.engine import get_serving_engine


def fetch_latest_analysis_batch_id() -> str | None:
    engine = get_serving_engine()
    with engine.begin() as connection:
        rows = connection.execute(
            select(
                analysis_batches.c.analysis_batch_id,
                analysis_batches.c.batch_status,
                analysis_batches.c.transformed_at,
                analysis_batches.c.updated_at,
                analysis_batches.c.created_at,
            )
        ).mappings().all()
    if not rows:
        return None

    preferred_rows = [row for row in rows if str(row.get("batch_status") or "") == "success"] or rows
    sorted_rows = sorted(
        preferred_rows,
        key=lambda row: (
            row.get("transformed_at") or row.get("updated_at") or row.get("created_at"),
            str(row.get("analysis_batch_id") or ""),
        ),
        reverse=True,
    )
    batch_id = sorted_rows[0].get("analysis_batch_id")
    return str(batch_id) if batch_id else None


def fetch_dashboard_summary_source_rows(
    analysis_batch_id: str,
    *,
    compare_snapshot_date: date,
) -> dict[str, list[dict[str, Any]]]:
    engine = get_serving_engine()
    with engine.begin() as connection:
        sales_rows = connection.execute(
            select(
                sales_orders.c.order_id,
                sales_orders.c.paid_at,
                sales_orders.c.paid_amount,
                sales_orders.c.payment_status,
            ).where(sales_orders.c.analysis_batch_id == analysis_batch_id)
        ).mappings().all()
        inventory_rows = connection.execute(
            select(
                inventory_current.c.sku_id,
                inventory_current.c.style_code,
                inventory_current.c.color_code,
                inventory_current.c.on_hand_qty,
                inventory_current.c.safe_stock_qty,
                inventory_current.c.season_tag,
                inventory_current.c.is_all_season,
                inventory_current.c.is_target_size,
                inventory_current.c.is_active_sale,
            ).where(inventory_current.c.analysis_batch_id == analysis_batch_id)
        ).mappings().all()
        compare_snapshot_rows = connection.execute(
            select(
                inventory_daily_snapshot.c.sku_id,
                inventory_daily_snapshot.c.style_code,
                inventory_daily_snapshot.c.color_code,
                inventory_daily_snapshot.c.on_hand_qty,
                inventory_daily_snapshot.c.safe_stock_qty,
                inventory_daily_snapshot.c.season_tag,
                inventory_daily_snapshot.c.is_all_season,
                inventory_daily_snapshot.c.is_target_size,
                inventory_daily_snapshot.c.is_active_sale,
            ).where(
                inventory_daily_snapshot.c.analysis_batch_id == analysis_batch_id,
                inventory_daily_snapshot.c.snapshot_date == compare_snapshot_date,
            )
        ).mappings().all()
        item_rows = connection.execute(
            select(
                sales_order_items.c.order_id,
                sales_order_items.c.quantity,
            ).where(sales_order_items.c.analysis_batch_id == analysis_batch_id)
        ).mappings().all()
    return {
        "sales_rows": [dict(row) for row in sales_rows],
        "inventory_rows": [dict(row) for row in inventory_rows],
        "compare_snapshot_rows": [dict(row) for row in compare_snapshot_rows],
        "item_rows": [dict(row) for row in item_rows],
    }
