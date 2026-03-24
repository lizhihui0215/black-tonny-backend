from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import require_admin_token
from app.schemas.common import ApiResponse
from app.schemas.cost_snapshot import CostSnapshotRequest, CostSnapshotResponse
from app.services.runtime import get_cost_snapshot_response, save_cost_snapshot


router = APIRouter(tags=["cost_snapshot"])


@router.get("/cost-snapshot", response_model=ApiResponse[CostSnapshotResponse])
def read_cost_snapshot() -> ApiResponse[CostSnapshotResponse]:
    return ApiResponse[CostSnapshotResponse].success(get_cost_snapshot_response())


@router.post(
    "/cost-snapshot",
    response_model=ApiResponse[CostSnapshotResponse],
    dependencies=[Depends(require_admin_token)],
)
def write_cost_snapshot(request: CostSnapshotRequest) -> ApiResponse[CostSnapshotResponse]:
    return ApiResponse[CostSnapshotResponse].success(save_cost_snapshot(request.snapshot))
