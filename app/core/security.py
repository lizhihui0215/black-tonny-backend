from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, Header, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.schemas.auth import FrontendTokenPayload


_FRONTEND_HTTP_BEARER = HTTPBearer(auto_error=False)


def _build_fernet(secret: str) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def _frontend_unauthorized(message: str) -> ApiError:
    return ApiError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code=40101,
        message=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def build_frontend_token_payload(
    *,
    home_path: str,
    roles: list[str],
    user_id: str,
    username: str,
) -> FrontendTokenPayload:
    now = int(time.time())
    settings = get_settings()
    return FrontendTokenPayload(
        userId=user_id,
        username=username,
        roles=roles,
        homePath=home_path,
        issuedAt=now,
        expiresAt=now + settings.frontend_auth_access_token_ttl_seconds,
    )


def issue_frontend_access_token(payload: FrontendTokenPayload) -> str:
    settings = get_settings()
    fernet = _build_fernet(settings.frontend_auth_secret)
    raw_payload = json.dumps(
        payload.model_dump(by_alias=True),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return fernet.encrypt(raw_payload).decode("utf-8")


def verify_frontend_access_token(token: str) -> FrontendTokenPayload:
    settings = get_settings()
    fernet = _build_fernet(settings.frontend_auth_secret)
    try:
        raw_payload = fernet.decrypt(token.encode("utf-8"))
        payload = FrontendTokenPayload.model_validate_json(raw_payload)
    except (InvalidToken, ValueError, TypeError) as error:
        raise _frontend_unauthorized("Invalid frontend access token.") from error

    if payload.expires_at <= int(time.time()):
        raise _frontend_unauthorized("Frontend access token has expired.")

    return payload


def require_frontend_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_FRONTEND_HTTP_BEARER),
) -> FrontendTokenPayload:
    if not credentials:
        raise _frontend_unauthorized("Frontend access token is required.")

    if credentials.scheme.lower() != "bearer":
        raise _frontend_unauthorized("Unsupported authorization scheme.")

    return verify_frontend_access_token(credentials.credentials)


def require_admin_token(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")
) -> None:
    settings = get_settings()
    if not x_admin_token or not secrets.compare_digest(
        x_admin_token, settings.admin_api_token
    ):
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=40110,
            message="Invalid admin token.",
        )
