from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, text

from app.db.base import (
    analysis_batches,
    capture_batches,
    capture_endpoint_payloads,
    cost_snapshots,
    inventory_current,
    inventory_daily_snapshot,
    job_runs,
    job_steps,
    payload_cache_index,
    sales_order_items,
    sales_orders,
)
from app.db.engine import get_capture_engine, get_serving_engine


def _build_database_summary(engine, table_map: dict[str, object]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "connected": False,
        "database_name": engine.url.database,
        "dialect": engine.dialect.name,
        "driver": engine.dialect.driver,
        "table_counts": {name: 0 for name in table_map},
        "table_counts_text": " / ".join("0" for _ in table_map),
    }

    try:
        with engine.begin() as connection:
            connection.execute(text("SELECT 1"))
            counts = {
                name: int(connection.execute(select(func.count()).select_from(table)).scalar_one())
                for name, table in table_map.items()
            }
        summary["connected"] = True
        summary["table_counts"] = counts
        summary["table_counts_text"] = " / ".join(str(counts[key]) for key in table_map)
    except Exception as error:  # noqa: BLE001
        summary["error"] = str(error)

    return summary


def fetch_serving_database_summary() -> dict[str, Any]:
    return _build_database_summary(
        get_serving_engine(),
        {
            "job_runs": job_runs,
            "job_steps": job_steps,
            "cost_snapshots": cost_snapshots,
            "payload_cache_index": payload_cache_index,
            "analysis_batches": analysis_batches,
            "sales_orders": sales_orders,
            "sales_order_items": sales_order_items,
            "inventory_current": inventory_current,
            "inventory_daily_snapshot": inventory_daily_snapshot,
        },
    )


def fetch_capture_database_summary() -> dict[str, Any]:
    return _build_database_summary(
        get_capture_engine(),
        {
            "capture_batches": capture_batches,
            "capture_endpoint_payloads": capture_endpoint_payloads,
        },
    )
