from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.core.security import require_admin_token
from app.jobs.rebuild import run_rebuild_job
from app.schemas.jobs import JobStatusResponse, RebuildJobRequest
from app.services.job_service import create_rebuild_job, get_job


router = APIRouter(tags=["jobs"])


@router.post("/jobs/rebuild", response_model=JobStatusResponse, dependencies=[Depends(require_admin_token)])
def enqueue_rebuild_job(
    payload: RebuildJobRequest,
    background_tasks: BackgroundTasks,
) -> JobStatusResponse:
    job = create_rebuild_job(payload)
    background_tasks.add_task(run_rebuild_job, job.job_id)
    return job


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def read_job(job_id: str) -> JobStatusResponse:
    try:
        return get_job(job_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}") from error

