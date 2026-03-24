from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update

from app.db.base import cost_snapshots
from app.db.engine import get_serving_engine


def list_cost_snapshot_rows() -> list[dict[str, Any]]:
    engine = get_serving_engine()
    with engine.begin() as connection:
        rows = connection.execute(
            select(cost_snapshots).order_by(cost_snapshots.c.snapshot_datetime.desc(), cost_snapshots.c.updated_at.desc())
        ).mappings().all()
    return [dict(row) for row in rows]


def cost_snapshot_period_exists(snapshot_period: str) -> bool:
    engine = get_serving_engine()
    with engine.begin() as connection:
        row = connection.execute(
            select(cost_snapshots.c.id).where(cost_snapshots.c.snapshot_period == snapshot_period)
        ).first()
    return row is not None


def insert_cost_snapshot_row(**values: Any) -> None:
    engine = get_serving_engine()
    with engine.begin() as connection:
        connection.execute(insert(cost_snapshots).values(**values))


def update_cost_snapshot_row(snapshot_period: str, **values: Any) -> None:
    engine = get_serving_engine()
    with engine.begin() as connection:
        connection.execute(
            update(cost_snapshots).where(cost_snapshots.c.snapshot_period == snapshot_period).values(**values)
        )
