from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import cost_snapshot, dashboard, health, jobs, manifest, pages, status


api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(status.router)
api_router.include_router(manifest.router)
api_router.include_router(pages.router)
api_router.include_router(dashboard.router)
api_router.include_router(cost_snapshot.router)
api_router.include_router(jobs.router)
