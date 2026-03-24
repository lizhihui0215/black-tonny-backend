from __future__ import annotations

"""FastAPI router assembly.

This package follows the boilerplate-style `api -> v1 -> routes` layout while
keeping the current public API contract at `/api/*`.
"""

from fastapi import APIRouter

from app.api.v1 import router as v1_router


router = APIRouter(prefix="/api")
router.include_router(v1_router)

__all__ = ["router"]
