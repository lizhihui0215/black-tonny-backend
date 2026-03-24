from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, insert, select

from app.db.base import payload_cache_index
from app.db.engine import get_serving_engine


def fetch_payload_cache_rows() -> list[dict[str, Any]]:
    engine = get_serving_engine()
    with engine.begin() as connection:
        rows = connection.execute(select(payload_cache_index)).mappings().all()
    return [dict(row) for row in rows]


def replace_payload_cache_index(rows: Sequence[dict[str, Any]]) -> None:
    engine = get_serving_engine()
    with engine.begin() as connection:
        connection.execute(delete(payload_cache_index))
        if rows:
            connection.execute(insert(payload_cache_index), list(rows))
