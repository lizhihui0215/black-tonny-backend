from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


JsonDict = dict[str, Any]

