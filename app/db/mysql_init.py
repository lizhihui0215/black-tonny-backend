from __future__ import annotations

from sqlalchemy import text

from app.db.engine import get_capture_engine, get_serving_engine


def ensure_databases_exist() -> None:
    """Ping both capture and serving databases as an explicit bootstrap hook."""
    for engine in (get_capture_engine(), get_serving_engine()):
        with engine.begin() as connection:
            connection.execute(text("SELECT 1"))
