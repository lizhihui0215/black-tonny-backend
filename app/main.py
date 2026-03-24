from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.api import router
from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.core.logging import configure_logging
from app.db.engine import init_databases
from app.services.runtime import ensure_payload_directories, get_status, render_homepage


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    ensure_payload_directories()
    init_databases()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(router)


@app.exception_handler(ApiError)
async def handle_api_error(_: Request, error: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "code": error.code,
            "data": None,
            "message": error.message,
        },
        headers=error.headers,
    )


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def read_root() -> str:
    return render_homepage(get_status())
