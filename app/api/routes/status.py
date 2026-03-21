from __future__ import annotations

from fastapi import APIRouter

from app.services.status_service import get_status


router = APIRouter(tags=["status"])


@router.get("/status")
def read_status() -> dict[str, object]:
    return get_status()

