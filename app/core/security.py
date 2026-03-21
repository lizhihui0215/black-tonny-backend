from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def require_admin_token(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")
) -> None:
    settings = get_settings()
    if x_admin_token != settings.admin_api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token.",
        )
