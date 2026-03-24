from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update

from app.db.base import analysis_batches
from app.db.engine import get_serving_engine


def analysis_batch_exists(analysis_batch_id: str) -> bool:
    engine = get_serving_engine()
    with engine.begin() as connection:
        existing = connection.execute(
            select(analysis_batches.c.analysis_batch_id).where(
                analysis_batches.c.analysis_batch_id == analysis_batch_id
            )
        ).first()
    return existing is not None


def insert_analysis_batch_row(**values: Any) -> None:
    engine = get_serving_engine()
    with engine.begin() as connection:
        connection.execute(insert(analysis_batches).values(**values))


def update_analysis_batch_row(analysis_batch_id: str, **values: Any) -> None:
    engine = get_serving_engine()
    with engine.begin() as connection:
        connection.execute(
            update(analysis_batches)
            .where(analysis_batches.c.analysis_batch_id == analysis_batch_id)
            .values(**values)
        )
