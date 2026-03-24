from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update

from app.db.base import job_runs, job_steps
from app.db.engine import get_serving_engine


def insert_job_run_row(**values: Any) -> None:
    engine = get_serving_engine()
    with engine.begin() as connection:
        connection.execute(insert(job_runs).values(**values))


def insert_job_step_row(**values: Any) -> None:
    engine = get_serving_engine()
    with engine.begin() as connection:
        connection.execute(insert(job_steps).values(**values))


def update_job_run_row(job_id: str, **values: Any) -> None:
    engine = get_serving_engine()
    with engine.begin() as connection:
        connection.execute(update(job_runs).where(job_runs.c.job_id == job_id).values(**values))


def fetch_job_run_row(job_id: str) -> dict[str, Any] | None:
    engine = get_serving_engine()
    with engine.begin() as connection:
        row = connection.execute(select(job_runs).where(job_runs.c.job_id == job_id)).mappings().first()
    return dict(row) if row else None


def list_job_step_rows(job_id: str) -> list[dict[str, Any]]:
    engine = get_serving_engine()
    with engine.begin() as connection:
        rows = connection.execute(
            select(job_steps).where(job_steps.c.job_id == job_id).order_by(job_steps.c.id.asc())
        ).mappings().all()
    return [dict(row) for row in rows]


def fetch_latest_job_id() -> str | None:
    engine = get_serving_engine()
    with engine.begin() as connection:
        row = connection.execute(select(job_runs.c.job_id).order_by(job_runs.c.created_at.desc()).limit(1)).first()
    if not row:
        return None
    return str(row[0])
