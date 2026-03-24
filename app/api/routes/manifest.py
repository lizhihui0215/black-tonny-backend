from __future__ import annotations

from fastapi import APIRouter
from app.schemas.common import ApiResponse
from app.schemas.manifest import ManifestResponse
from app.services.runtime import get_manifest


router = APIRouter(tags=["manifest"])


@router.get("/manifest", response_model=ApiResponse[ManifestResponse])
def read_manifest() -> ApiResponse[ManifestResponse]:
    return ApiResponse[ManifestResponse].success(get_manifest())
