from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import require_admin_token
from app.schemas.cost_snapshot import CostSnapshotRequest, CostSnapshotResponse
from app.services.cost_service import get_cost_snapshot_response, save_cost_snapshot


router = APIRouter(tags=["cost_snapshot"])


@router.get("/cost-snapshot", response_model=CostSnapshotResponse)
def read_cost_snapshot() -> CostSnapshotResponse:
    return get_cost_snapshot_response()


@router.post("/cost-snapshot", response_model=CostSnapshotResponse, dependencies=[Depends(require_admin_token)])
def write_cost_snapshot(request: CostSnapshotRequest) -> CostSnapshotResponse:
    return save_cost_snapshot(request.snapshot)

