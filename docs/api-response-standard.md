# API 响应标准

本文件定义 `black-tonny-backend` 当前正式 `/api/*` 接口的默认响应标准。

它的目标是：

- 统一前后端对正式业务接口的成功响应形状
- 让前端可以直接复用 `vben` 默认请求链路
- 避免不同接口各自返回不同顶层结构

## 1. 默认成功响应

正式业务接口默认返回：

```json
{
  "code": 0,
  "data": {},
  "message": "ok"
}
```

字段含义：

- `code`
  - `0` 表示成功
- `data`
  - 真正的业务数据载荷
- `message`
  - 响应消息，当前成功默认返回 `ok`

## 2. 适用范围

默认适用于当前 backend 暴露给前端或管理端消费的正式业务接口，例如：

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/codes`
- `GET /api/user/info`
- `GET /api/manifest`
- `GET /api/pages/{page_key}`
- `GET /api/dashboard/summary`
- `POST /api/assistant/chat`
- `GET /api/status`
- `POST /api/jobs/rebuild`
- `GET /api/jobs/{job_id}`
- `GET /api/cost-snapshot`
- `POST /api/cost-snapshot`

## 3. 当前例外

以下接口当前可以不走这套 envelope：

- `GET /api/health`

原因：

- 它的定位是基础健康探针
- 主要服务轻量监测和可达性判断
- 不属于前端业务数据主链

如果未来某个探针接口开始承担正式业务数据职责，再评估是否纳入统一 envelope。

## 4. 错误响应

当前默认规则是：

- 成功请求使用 `{ code, data, message }`
- 错误请求继续使用正常 HTTP 状态码与 FastAPI 异常响应
- auth 或 token 校验失败时，允许使用 `401 + { code, data: null, message }`

也就是说：

- 不要求把所有错误也包装成 `200 + code != 0`
- `404 / 422 / 401 / 403 / 500` 等错误继续按 HTTP 语义返回

## 5. 前端协作约定

和 frontend 的默认协作约定保持一致：

- 正式 `/api/*` 接口优先按这套 envelope 提供
- 前端正式接口默认使用 `requestClient`
- 不再为了裸响应长期保留前端特例解包逻辑
- 如果 frontend 先用 mock 定义尚未落地的正式业务接口，该 mock 也必须先返回同一套 `{ code, data, message }`
- frontend `backend-mock` 只能作为前置契约实现、单仓开发 fallback 和联调样本，不能长期替代 backend 正式接口
- frontend 登录相关 fallback mock 也必须继续复用 backend 已存在的 `/api/auth/*` 与 `/api/user/info` 路径和同一套 envelope，不能再发明平行登录契约

## 6. 变更规则

如果新增正式业务 API：

1. 默认先使用这套 `{ code, data, message }` 标准
2. 如果确实要偏离，必须在对应接口文档里明确写出原因
3. 同步更新受影响的 frontend / backend 标准文档
