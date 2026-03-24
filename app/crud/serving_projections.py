from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, insert

from app.db.base import (
    inventory_current,
    inventory_daily_snapshot,
    sales_order_items,
    sales_orders,
)
from app.db.engine import get_serving_engine


def replace_summary_projection_rows(
    *,
    analysis_batch_id: str,
    sales_orders_rows: Sequence[dict[str, Any]],
    sales_order_items_rows: Sequence[dict[str, Any]],
    inventory_current_rows: Sequence[dict[str, Any]],
    inventory_daily_snapshot_rows: Sequence[dict[str, Any]],
) -> None:
    engine = get_serving_engine()
    with engine.begin() as connection:
        connection.execute(delete(sales_order_items).where(sales_order_items.c.analysis_batch_id == analysis_batch_id))
        connection.execute(delete(sales_orders).where(sales_orders.c.analysis_batch_id == analysis_batch_id))
        connection.execute(delete(inventory_current).where(inventory_current.c.analysis_batch_id == analysis_batch_id))
        connection.execute(
            delete(inventory_daily_snapshot).where(
                inventory_daily_snapshot.c.analysis_batch_id == analysis_batch_id
            )
        )

        if sales_orders_rows:
            connection.execute(insert(sales_orders), list(sales_orders_rows))
        if sales_order_items_rows:
            connection.execute(insert(sales_order_items), list(sales_order_items_rows))
        if inventory_current_rows:
            connection.execute(insert(inventory_current), list(inventory_current_rows))
        if inventory_daily_snapshot_rows:
            connection.execute(insert(inventory_daily_snapshot), list(inventory_daily_snapshot_rows))
