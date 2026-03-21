from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
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


def clear_engine_caches() -> None:
    get_capture_engine.cache_clear()
    get_serving_engine.cache_clear()
