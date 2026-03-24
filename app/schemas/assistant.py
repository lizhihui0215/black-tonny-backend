from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(item.capitalize() for item in tail)


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class AssistantAction(CamelModel):
    note: str | None = None
    title: str


class AssistantContext(CamelModel):
    actions: list[AssistantAction] = Field(default_factory=list)
    description: str | None = None
    guardrails: list[str] = Field(default_factory=list)
    headline: str | None = None
    metrics: list[str] = Field(default_factory=list)
    page_key: str
    page_title: str
    prompts: list[str] = Field(default_factory=list)
    risk_points: list[str] = Field(default_factory=list)
    source_note: str | None = None
    staff_tips: list[str] = Field(default_factory=list)
    summary: str | None = None


class AssistantChatMessage(CamelModel):
    content: str
    role: Literal["assistant", "user"]


class AssistantChatRequest(CamelModel):
    context: AssistantContext | None = None
    prompt: str
    recent_messages: list[AssistantChatMessage] = Field(default_factory=list)


class AssistantChatResponse(CamelModel):
    grounded: bool = True
    provider: str = "backend-context"
    reply: str


ASSISTANT_CHAT_SUCCESS_RESPONSE_EXAMPLE = {
    "code": 0,
    "message": "ok",
    "data": {
        "reply": "经营总览这页我建议先按这个顺序推进：\n1. 先看 summary，再决定是否下钻到趋势和库存模块。 先用顶部 8 张卡确认结果、效率和库存风险。\n2. 切日期时优先看销售类卡片变化，再看库存类副值变化。 当前页统一跟随日期区间变化。",
        "provider": "backend-context",
        "grounded": True,
    },
}
