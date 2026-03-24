from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FrontendLoginRequest(BaseModel):
    password: str = Field(min_length=1)
    username: str = Field(min_length=1)


class FrontendLoginResponse(BaseModel):
    access_token: str = Field(alias="accessToken")

    model_config = ConfigDict(populate_by_name=True)


class FrontendLogoutResponse(BaseModel):
    success: bool = True


class FrontendTokenPayload(BaseModel):
    expires_at: int = Field(alias="expiresAt")
    home_path: str = Field(alias="homePath")
    issued_at: int = Field(alias="issuedAt")
    roles: list[str]
    user_id: str = Field(alias="userId")
    username: str

    model_config = ConfigDict(populate_by_name=True)
