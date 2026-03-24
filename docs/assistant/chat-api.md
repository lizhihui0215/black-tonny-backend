# Assistant Chat API

本文件定义右侧 AI 助手当前正式聊天接口的契约和边界。

## Endpoint

- `POST /api/assistant/chat`
- 当前 runtime phase 不要求 frontend bearer access token
- 若未来重新启用 backend frontend auth，先更新 [frontend-auth-api.md](../frontend-auth-api.md) 与 [frontend-backend-boundary.md](../frontend-backend-boundary.md)，再同步恢复该接口的登录要求与路由依赖

成功响应遵循 backend 默认 envelope：

```json
{
  "code": 0,
  "data": {
    "reply": "string",
    "provider": "backend-context",
    "grounded": true
  },
  "message": "ok"
}
```

## Request Body

```json
{
  "prompt": "今天先看什么",
  "context": {
    "pageKey": "dashboard",
    "pageTitle": "经营总览",
    "summary": "先看顶部 8 张卡，再决定是否继续下钻。",
    "metrics": [
      "销售额 3.2 万，较上期 +12%",
      "订单数 182，较上期 +8%"
    ],
    "actions": [
      {
        "title": "先看 summary，再决定是否下钻到趋势和库存模块。",
        "note": "先用顶部 8 张卡确认结果、效率和库存风险。"
      }
    ],
    "riskPoints": [
      "低库存 SKU 12 个"
    ],
    "staffTips": [
      "先同步今天重点盯哪一张卡。"
    ],
    "sourceNote": "当前区间 2026-03-16 至 2026-03-22。"
  },
  "recentMessages": [
    {
      "role": "assistant",
      "content": "我会优先基于当前页已加载内容回答。"
    }
  ]
}
```

## Current Rule

- `prompt` 由 frontend 发送用户当前问题
- `context` 由当前页面已加载的业务上下文组成
- `recentMessages` 当前主要用于预留线程上下文，不参与复杂多轮推理
- backend 当前使用“基于页面上下文的确定性回复”作为正式实现
- 后续若接入真实 DeepSeek，仅替换 backend provider，不改 frontend 调用入口
- 当前 runtime phase 未登录也可调用该接口；若未来切回 backend frontend auth，再同步更新本文件与实际路由依赖

## Ownership

- frontend 负责右侧栏 UI、上下文采集、线程展示和输入体验
- backend 负责聊天接口契约、上下文解释逻辑和后续模型 provider 接入
- frontend 不应直接调用外部模型 API

## Fallback Rule

- 正式链路是 frontend -> `POST /api/assistant/chat`
- 若 backend 在本地联调场景暂未启动，frontend 可以保留本地兜底回复
- 该本地兜底仅用于可用性，不是正式业务契约源
