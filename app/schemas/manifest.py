from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ManifestResponse(BaseModel):
    generated_at: Optional[str] = None
    date_tag: Optional[str] = None
    store_name: Optional[str] = None
    analysis_batch_id: Optional[str] = None
    available_pages: dict[str, str] = Field(default_factory=dict)
    available_exports: dict[str, str] = Field(default_factory=dict)
    pipeline: list[str] = Field(default_factory=list)
