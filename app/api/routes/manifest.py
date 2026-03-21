from __future__ import annotations

from fastapi import APIRouter

from app.schemas.manifest import ManifestResponse
from app.services.payload_service import get_manifest


router = APIRouter(tags=["manifest"])


@router.get("/manifest", response_model=ManifestResponse)
def read_manifest() -> ManifestResponse:
    return get_manifest()

