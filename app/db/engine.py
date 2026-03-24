from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings
from app.db.base import capture_metadata, serving_metadata


@lru_cache
def get_capture_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.capture_database_url, future=True, pool_pre_ping=True)


@lru_cache
def get_serving_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.serving_database_url, future=True, pool_pre_ping=True)


def init_databases() -> None:
    serving_metadata.create_all(get_serving_engine())
    capture_metadata.create_all(get_capture_engine())
    _ensure_capture_route_kind_column(get_capture_engine())
    _ensure_capture_large_text_columns(get_capture_engine())


def _ensure_capture_route_kind_column(engine: Engine) -> None:
    inspector = inspect(engine)
    try:
        columns = {column["name"] for column in inspector.get_columns("capture_endpoint_payloads")}
    except Exception:
        return
    if "route_kind" in columns:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE capture_endpoint_payloads ADD COLUMN route_kind VARCHAR(32)"))
        try:
            connection.execute(
                text(
                    "CREATE INDEX ix_capture_endpoint_payloads_route_kind "
                    "ON capture_endpoint_payloads (route_kind)"
                )
            )
        except Exception:
            # Some databases may auto-create or reject duplicate index names; the column itself is the priority.
            pass


def _ensure_capture_large_text_columns(engine: Engine) -> None:
    if engine.dialect.name != "mysql":
        return

    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT COLUMN_NAME, COLUMN_TYPE
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'capture_endpoint_payloads'
                      AND COLUMN_NAME IN ('payload_json', 'request_params')
                    """
                )
            ).fetchall()
    except Exception:
        return

    columns = {str(name): str(column_type).lower() for name, column_type in rows}

    alterations = []
    if columns.get("payload_json") == "text":
        alterations.append("MODIFY COLUMN payload_json LONGTEXT NOT NULL")
    if columns.get("request_params") == "text":
        alterations.append("MODIFY COLUMN request_params LONGTEXT NULL")
    if not alterations:
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE capture_endpoint_payloads "
                + ", ".join(alterations)
            )
        )


def clear_engine_caches() -> None:
    get_capture_engine.cache_clear()
    get_serving_engine.cache_clear()
