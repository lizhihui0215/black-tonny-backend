from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.core.security import require_admin_token
from app.jobs.rebuild import run_rebuild_job
from app.schemas.common import ApiResponse
from app.schemas.jobs import JobStatusResponse, RebuildJobRequest
from app.services.runtime import create_rebuild_job, get_job


router = APIRouter(tags=["jobs"])


@router.post(
    "/jobs/rebuild",
    response_model=ApiResponse[JobStatusResponse],
    dependencies=[Depends(require_admin_token)],
)
def enqueue_rebuild_job(
    payload: RebuildJobRequest,
    background_tasks: BackgroundTasks,
) -> ApiResponse[JobStatusResponse]:
    job = create_rebuild_job(payload)
    background_tasks.add_task(run_rebuild_job, job.job_id)
    return ApiResponse[JobStatusResponse].success(job)


@router.get("/jobs/{job_id}", response_model=ApiResponse[JobStatusResponse])
def read_job(job_id: str) -> ApiResponse[JobStatusResponse]:
    try:
        return ApiResponse[JobStatusResponse].success(get_job(job_id))
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}") from error
