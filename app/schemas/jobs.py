from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RebuildJobRequest(BaseModel):
    sync_mode: str = "full"
    sync_start_date: Optional[str] = None
    sync_end_date: Optional[str] = None
    build_only: bool = False


class JobStepResponse(BaseModel):
    title: str
    status: str
    detail: str
    created_at: str


class JobStatusResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    message: str
    sync_mode: Optional[str] = None
    sync_start_date: Optional[str] = None
    sync_end_date: Optional[str] = None
    build_only: bool = False
    requested_by: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    last_error: Optional[str] = None
    steps: list[JobStepResponse] = Field(default_factory=list)
