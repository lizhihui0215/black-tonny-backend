from __future__ import annotations

from app.core.config import get_settings


def get_rebuild_cron() -> str:
    return get_settings().rebuild_cron

