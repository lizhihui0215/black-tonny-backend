from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    assistant,
    auth,
    cost_snapshot,
    dashboard,
    health,
    jobs,
    manifest,
    pages,
    status,
    user,
)

# NOTE:
# We introduce the boilerplate-style `app.api.v1` package now, but intentionally
# keep the public path contract at `/api/*` instead of `/api/v1/*`.
# A real external version-prefix rollout must be a separate contract change.
router = APIRouter()
router.include_router(health.router)
router.include_router(status.router)
router.include_router(auth.router)
router.include_router(user.router)
router.include_router(manifest.router)
router.include_router(pages.router)
router.include_router(dashboard.router)
router.include_router(assistant.router)
router.include_router(cost_snapshot.router)
router.include_router(jobs.router)
