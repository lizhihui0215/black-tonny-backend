from __future__ import annotations

from typing import Optional
from uuid import uuid4

from sqlalchemy import insert, select, update

from app.core.timezone import now_local
from app.db.base import job_runs, job_steps
from app.db.engine import get_serving_engine
from app.schemas.jobs import JobStatusResponse, JobStepResponse, RebuildJobRequest


def create_rebuild_job(payload: RebuildJobRequest, requested_by: str = "api") -> JobStatusResponse:
    job_id = uuid4().hex
    now = now_local()
    engine = get_serving_engine()
    with engine.begin() as connection:
        connection.execute(
            insert(job_runs).values(
                job_id=job_id,
                job_type="rebuild",
                status="queued",
                message="Rebuild job queued.",
                sync_mode=payload.sync_mode,
                sync_start_date=payload.sync_start_date,
                sync_end_date=payload.sync_end_date,
                build_only=payload.build_only,
                requested_by=requested_by,
                created_at=now,
                started_at=None,
                finished_at=None,
                last_error=None,
            )
        )
        connection.execute(
            insert(job_steps).values(
                job_id=job_id,
                title="排队启动",
                status="queued",
                detail="已接收重建请求，等待开始执行。",
                created_at=now,
            )
        )
    return get_job(job_id)


def add_job_step(job_id: str, title: str, status: str, detail: str) -> None:
    engine = get_serving_engine()
    with engine.begin() as connection:
        connection.execute(
            insert(job_steps).values(
                job_id=job_id,
                title=title,
                status=status,
                detail=detail,
                created_at=now_local(),
            )
        )


def update_job(
    job_id: str,
    *,
    status: str,
    message: str,
    started: bool = False,
    finished: bool = False,
    last_error: Optional[str] = None,
) -> None:
    values: dict[str, object] = {
        "status": status,
        "message": message,
        "last_error": last_error,
    }
    if started:
        values["started_at"] = now_local()
    if finished:
        values["finished_at"] = now_local()
    engine = get_serving_engine()
    with engine.begin() as connection:
        connection.execute(update(job_runs).where(job_runs.c.job_id == job_id).values(**values))


def get_job(job_id: str) -> JobStatusResponse:
    engine = get_serving_engine()
    with engine.begin() as connection:
        job_row = connection.execute(
            select(job_runs).where(job_runs.c.job_id == job_id)
        ).mappings().first()
        if not job_row:
            raise KeyError(job_id)
        step_rows = connection.execute(
            select(job_steps).where(job_steps.c.job_id == job_id).order_by(job_steps.c.id.asc())
        ).mappings().all()
    return JobStatusResponse(
        job_id=str(job_row["job_id"]),
        job_type=str(job_row["job_type"]),
        status=str(job_row["status"]),
        message=str(job_row["message"]),
        sync_mode=job_row["sync_mode"],
        sync_start_date=job_row["sync_start_date"],
        sync_end_date=job_row["sync_end_date"],
        build_only=bool(job_row["build_only"]),
        requested_by=str(job_row["requested_by"]),
        created_at=job_row["created_at"].isoformat(),
        started_at=job_row["started_at"].isoformat() if job_row["started_at"] else None,
        finished_at=job_row["finished_at"].isoformat() if job_row["finished_at"] else None,
        last_error=str(job_row["last_error"]) if job_row["last_error"] else None,
        steps=[
            JobStepResponse(
                title=str(row["title"]),
                status=str(row["status"]),
                detail=str(row["detail"]),
                created_at=row["created_at"].isoformat(),
            )
            for row in step_rows
        ],
    )


def get_latest_job() -> Optional[JobStatusResponse]:
    engine = get_serving_engine()
    with engine.begin() as connection:
        row = connection.execute(
            select(job_runs.c.job_id).order_by(job_runs.c.created_at.desc()).limit(1)
        ).first()
    if not row:
        return None
    return get_job(str(row[0]))
