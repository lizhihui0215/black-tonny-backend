from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.engine import init_app_database
from app.services.homepage_service import render_homepage
from app.services.payload_service import ensure_payload_directories
from app.services.status_service import get_status


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    ensure_payload_directories()
    init_app_database()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(api_router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def read_root() -> str:
    return render_homepage(get_status())
