from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CostSnapshotRequest(BaseModel):
    snapshot: dict[str, Any]


class CostSnapshotResponse(BaseModel):
    snapshot: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list)

