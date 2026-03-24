from __future__ import annotations

import re

from app.schemas.assistant import AssistantChatRequest, AssistantChatResponse, AssistantContext


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def pick_prompt_matches(items: list[str], prompt: str) -> list[str]:
    normalized = clean_text(prompt)
    keywords = ["补货", "会员", "去化", "库存", "店员", "清货", "风险"]
    matched_keyword = next((keyword for keyword in keywords if keyword in normalized), None)

    if not matched_keyword:
        return items

    matched_items = [item for item in items if matched_keyword in item]
    return matched_items if matched_items else items


def build_fallback_reply(context: AssistantContext) -> str:
    metrics = context.metrics[:3]

    lines = [
        f"我现在拿到的是「{context.page_title}」页面上下文。",
        f"当前主判断：{clean_text(context.headline)}" if context.headline else "",
        (
            f"补充说明：{clean_text(context.summary)}"
            if context.summary
            else (f"补充说明：{clean_text(context.description)}" if context.description else "")
        ),
        f"先看：{'；'.join(metrics)}" if metrics else "",
    ]

    return "\n".join(line for line in lines if line)


def build_action_reply(context: AssistantContext, prompt: str) -> str:
    lines = [f"{item.title} {item.note}" if item.note else item.title for item in context.actions]
    matched = pick_prompt_matches(lines, prompt)[:3]

    if not matched:
        return build_fallback_reply(context)

    rows = [
        f"{context.page_title}这页我建议先按这个顺序推进：",
        *[f"{index + 1}. {item}" for index, item in enumerate(matched)],
        f"判断依据：{clean_text(context.summary)}" if context.summary else "",
    ]
    return "\n".join(row for row in rows if row)


def build_risk_reply(context: AssistantContext, prompt: str) -> str:
    matched = pick_prompt_matches(context.risk_points, prompt)[:3]

    if not matched:
        return build_fallback_reply(context)

    rows = [
        "当前最该先盯的风险点有：",
        *[f"{index + 1}. {item}" for index, item in enumerate(matched)],
        f"数据提示：{context.source_note}" if context.source_note else "",
    ]
    return "\n".join(row for row in rows if row)


def build_staff_reply(context: AssistantContext) -> str:
    tips = context.staff_tips[:3]

    if not tips:
        return build_fallback_reply(context)

    return "\n".join(
        [
            "如果你要拿这页内容去开晨会，我建议这样同步：",
            *[f"{index + 1}. {item}" for index, item in enumerate(tips)],
        ]
    )


def build_guardrail_reply(context: AssistantContext) -> str:
    lines = context.guardrails[:4]

    if not lines and not context.source_note:
        return build_fallback_reply(context)

    rows = [
        "这块我会按下面的边界来回答：",
        *[f"{index + 1}. {item}" for index, item in enumerate(lines)],
        f"当前上下文：{context.source_note}" if context.source_note else "",
    ]
    return "\n".join(row for row in rows if row)


def build_metric_reply(context: AssistantContext) -> str:
    metrics = context.metrics[:4]

    if not metrics:
        return build_fallback_reply(context)

    rows = [
        "这页我会先抓这几条核心信息：",
        *[f"{index + 1}. {item}" for index, item in enumerate(metrics)],
        f"整体判断：{clean_text(context.summary)}" if context.summary else "",
    ]
    return "\n".join(row for row in rows if row)


def resolve_assistant_reply(prompt: str, context: AssistantContext | None) -> str:
    if context is None:
        return (
            "DeepSeek 面板已经打开，但当前页面还没把业务上下文传进来。"
            "你可以先切到经营页面，或者问我“今天先看什么”。"
        )

    normalized = clean_text(prompt)

    if re.search(r"今天|先做|优先|动作|安排", normalized):
        return build_action_reply(context, normalized)

    if re.search(r"为什么|原因|重点|风险|异常", normalized):
        return build_risk_reply(context, normalized)

    if re.search(r"店员|晨会|话术|同步", normalized):
        return build_staff_reply(context)

    if re.search(r"数据|口径|可信|注意", normalized):
        return build_guardrail_reply(context)

    if re.search(r"指标|数据点|看什么|summary|概览", normalized):
        return build_metric_reply(context)

    if re.search(r"补货|清货|去化|会员|库存", normalized):
        return build_action_reply(context, normalized)

    return build_fallback_reply(context)


def get_assistant_chat_response(payload: AssistantChatRequest) -> AssistantChatResponse:
    reply = resolve_assistant_reply(payload.prompt, payload.context)
    return AssistantChatResponse(reply=reply)
