from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update

from app.db.base import capture_batches, capture_endpoint_payloads
from app.db.engine import get_capture_engine


def capture_batch_exists(capture_batch_id: str) -> bool:
    engine = get_capture_engine()
    with engine.begin() as connection:
        existing = connection.execute(
            select(capture_batches.c.capture_batch_id).where(capture_batches.c.capture_batch_id == capture_batch_id)
        ).first()
    return existing is not None


def fetch_capture_batch_row(capture_batch_id: str) -> dict[str, Any] | None:
    engine = get_capture_engine()
    with engine.begin() as connection:
        row = connection.execute(
            select(capture_batches).where(capture_batches.c.capture_batch_id == capture_batch_id)
        ).mappings().first()
    return dict(row) if row else None


def insert_capture_batch_row(**values: Any) -> None:
    engine = get_capture_engine()
    with engine.begin() as connection:
        connection.execute(insert(capture_batches).values(**values))


def update_capture_batch_row(capture_batch_id: str, **values: Any) -> None:
    engine = get_capture_engine()
    with engine.begin() as connection:
        connection.execute(
            update(capture_batches)
            .where(capture_batches.c.capture_batch_id == capture_batch_id)
            .values(**values)
        )


def insert_capture_endpoint_payload_row(**values: Any) -> None:
    engine = get_capture_engine()
    with engine.begin() as connection:
        connection.execute(insert(capture_endpoint_payloads).values(**values))


def list_capture_endpoint_payload_rows(capture_batch_id: str) -> list[dict[str, Any]]:
    engine = get_capture_engine()
    with engine.begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.source_endpoint.asc(), capture_endpoint_payloads.c.page_no.asc())
        ).mappings().all()
    return [dict(row) for row in rows]
