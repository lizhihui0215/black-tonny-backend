from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FrontendUserInfoResponse(BaseModel):
    avatar: str
    desc: str
    home_path: str = Field(alias="homePath")
    real_name: str = Field(alias="realName")
    roles: list[str]
    token: str
    user_id: str = Field(alias="userId")
    username: str

    model_config = ConfigDict(populate_by_name=True)
