from __future__ import annotations

import secrets

from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.core.security import build_frontend_token_payload, issue_frontend_access_token
from app.schemas.auth import FrontendTokenPayload
from app.schemas.user import FrontendUserInfoResponse


FRONTEND_ACCESS_CODES = ["black-tonny"]
FRONTEND_OWNER_ROLE = "owner"
FRONTEND_OWNER_USER_ID = "black-tonny-owner"


def _build_owner_profile() -> dict[str, object]:
    settings = get_settings()
    return {
        "avatar": settings.owner_login_avatar_url,
        "desc": "Black Tonny 店主账号",
        "homePath": settings.owner_login_home_path,
        "realName": settings.owner_login_real_name,
        "roles": [FRONTEND_OWNER_ROLE],
        "userId": FRONTEND_OWNER_USER_ID,
        "username": settings.owner_login_username,
    }


def authenticate_owner(username: str, password: str) -> str:
    settings = get_settings()
    if not secrets.compare_digest(username, settings.owner_login_username) or not secrets.compare_digest(
        password, settings.owner_login_password
    ):
        raise ApiError(
            status_code=401,
            code=40120,
            message="Invalid username or password.",
        )

    profile = _build_owner_profile()
    payload = build_frontend_token_payload(
        home_path=str(profile["homePath"]),
        roles=list(profile["roles"]),
        user_id=str(profile["userId"]),
        username=str(profile["username"]),
    )
    return issue_frontend_access_token(payload)


def get_frontend_access_codes() -> list[str]:
    return FRONTEND_ACCESS_CODES.copy()


def build_frontend_user_info(
    token_payload: FrontendTokenPayload,
    *,
    access_token: str,
) -> FrontendUserInfoResponse:
    profile = _build_owner_profile()
    return FrontendUserInfoResponse(
        avatar=str(profile["avatar"]),
        desc=str(profile["desc"]),
        homePath=token_payload.home_path,
        realName=str(profile["realName"]),
        roles=token_payload.roles,
        token=access_token,
        userId=token_payload.user_id,
        username=token_payload.username,
    )
