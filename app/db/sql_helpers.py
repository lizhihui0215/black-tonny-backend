from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection


def fetch_mapping_rows(
    connection: Connection,
    query: str,
    params: Optional[dict[str, object]] = None,
) -> list[dict[str, object]]:
    result = connection.execute(text(query), params or {})
    return [dict(row) for row in result.mappings().all()]
