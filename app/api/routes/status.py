from __future__ import annotations

from fastapi import APIRouter

from app.schemas.common import ApiResponse
from app.schemas.status import StatusResponse
from app.services.runtime import get_status


router = APIRouter(tags=["status"])


@router.get("/status", response_model=ApiResponse[StatusResponse])
def read_status() -> ApiResponse[StatusResponse]:
    return ApiResponse[StatusResponse].success(StatusResponse.model_validate(get_status()))
