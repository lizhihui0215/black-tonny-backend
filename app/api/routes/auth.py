from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import require_frontend_user
from app.schemas.auth import (
    FrontendLoginRequest,
    FrontendLoginResponse,
    FrontendLogoutResponse,
)
from app.schemas.common import ApiResponse
from app.services.runtime import authenticate_owner, get_frontend_access_codes


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=ApiResponse[FrontendLoginResponse])
def login(payload: FrontendLoginRequest) -> ApiResponse[FrontendLoginResponse]:
    access_token = authenticate_owner(payload.username, payload.password)
    return ApiResponse[FrontendLoginResponse].success(
        FrontendLoginResponse(accessToken=access_token)
    )


@router.post("/logout", response_model=ApiResponse[FrontendLogoutResponse])
def logout() -> ApiResponse[FrontendLogoutResponse]:
    return ApiResponse[FrontendLogoutResponse].success(FrontendLogoutResponse())


@router.get(
    "/codes",
    dependencies=[Depends(require_frontend_user)],
    response_model=ApiResponse[list[str]],
)
def read_access_codes() -> ApiResponse[list[str]]:
    return ApiResponse[list[str]].success(get_frontend_access_codes())
