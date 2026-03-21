from __future__ import annotations

from fastapi import APIRouter

from app.core.timezone import now_iso


router = APIRouter(tags=["health"])


@router.get("/health")
def get_health() -> dict[str, object]:
    return {"ok": True, "timestamp": now_iso()}

