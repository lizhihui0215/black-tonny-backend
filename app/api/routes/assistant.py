from __future__ import annotations

from fastapi import APIRouter
from app.schemas.assistant import (
    ASSISTANT_CHAT_SUCCESS_RESPONSE_EXAMPLE,
    AssistantChatRequest,
    AssistantChatResponse,
)
from app.schemas.common import ApiResponse
from app.services.runtime import get_assistant_chat_response


router = APIRouter(
    prefix="/assistant",
    tags=["assistant"],
)


@router.post(
    "/chat",
    response_model=ApiResponse[AssistantChatResponse],
    summary="基于当前页面上下文生成 AI 助手回复",
    responses={
        200: {
            "description": "右侧 AI 助手聊天回复",
            "content": {
                "application/json": {
                    "example": ASSISTANT_CHAT_SUCCESS_RESPONSE_EXAMPLE,
                }
            },
        }
    },
)
def chat_with_assistant(payload: AssistantChatRequest) -> ApiResponse[AssistantChatResponse]:
    return ApiResponse[AssistantChatResponse].success(get_assistant_chat_response(payload))
