from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


JsonDict = dict[str, Any]

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = Field(default=0, description="0 表示成功，其他表示失败")
    data: T
    message: str = Field(default="ok", description="响应消息")

    @classmethod
    def success(cls, data: T, message: str = "ok") -> "ApiResponse[T]":
        return cls(code=0, data=data, message=message)
