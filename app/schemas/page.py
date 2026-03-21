from __future__ import annotations

from typing import Any

from pydantic import Field

from app.schemas.common import FlexibleModel


class PagePayloadResponse(FlexibleModel):
    meta: dict[str, Any] = Field(default_factory=dict)
    summary_cards: dict[str, Any] = Field(default_factory=dict)
    today_focus: dict[str, Any] = Field(default_factory=dict)
    execution_board: dict[str, Any] = Field(default_factory=dict)
    health_lights: list[dict[str, Any]] = Field(default_factory=list)
    time_strategy: dict[str, Any] = Field(default_factory=dict)
    decision: dict[str, Any] = Field(default_factory=dict)
    consulting_analysis: dict[str, Any] = Field(default_factory=dict)
    ai_analysis: dict[str, Any] = Field(default_factory=dict)
    inventory_sales_relationship: dict[str, Any] = Field(default_factory=dict)
    dashboard_tips: list[Any] = Field(default_factory=list)
    insights: list[Any] = Field(default_factory=list)
    tables: dict[str, Any] = Field(default_factory=dict)

