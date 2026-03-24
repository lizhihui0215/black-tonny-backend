from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import require_frontend_user
from app.schemas.auth import FrontendTokenPayload
from app.schemas.common import ApiResponse
from app.schemas.user import FrontendUserInfoResponse
from app.services.runtime import build_frontend_user_info


router = APIRouter(prefix="/user", tags=["user"])
_HTTP_BEARER = HTTPBearer(auto_error=False)


@router.get("/info", response_model=ApiResponse[FrontendUserInfoResponse])
def read_user_info(
    token_payload: FrontendTokenPayload = Depends(require_frontend_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(_HTTP_BEARER),
) -> ApiResponse[FrontendUserInfoResponse]:
    access_token = credentials.credentials if credentials else ""
    return ApiResponse[FrontendUserInfoResponse].success(
        build_frontend_user_info(token_payload, access_token=access_token)
    )
