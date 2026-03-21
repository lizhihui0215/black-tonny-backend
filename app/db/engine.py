from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.core.config import get_settings
from app.db.base import metadata


@lru_cache
def get_app_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.app_db_url, future=True, pool_pre_ping=True)


def init_app_database() -> None:
    metadata.create_all(get_app_engine())


def clear_engine_cache() -> None:
    get_app_engine.cache_clear()

