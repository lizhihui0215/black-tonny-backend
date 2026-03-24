# Frontend Auth API

本文件定义当前 split frontend/backend 运行时已经启用的 backend frontend-auth 契约。

截至 2026-03-24，当前 runtime 事实是：

- frontend 正式登录主线已经走 backend `/api/auth/*` 与 `/api/user/info`
- frontend guard 与 access bootstrap 继续复用 `vben` 既有 `request/auth/router/store` 主链
- sibling frontend 仓库内的 `apps/backend-mock` 仍可保留同路径 fallback，但只作为单仓开发与 E2E fallback
- backend 正式业务接口 `manifest/pages/dashboard summary/assistant chat` 当前仍不要求 frontend bearer token

## 1. 当前正式契约

当前 frontend auth 正式运行主线是：

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/codes`
- `GET /api/user/info`

这些接口的职责分别是：

- `POST /api/auth/login`
  - 接收 frontend 登录页提交的 `username`、`password`
  - 返回 frontend access token
- `POST /api/auth/logout`
  - 作为 frontend 登出主线的正式接口
- `GET /api/auth/codes`
  - 给 frontend access store 返回 access code 列表
- `GET /api/user/info`
  - 给 frontend user store 与 guard bootstrap 返回 owner 用户信息

成功响应继续遵循：

```json
{
  "code": 0,
  "data": {},
  "message": "ok"
}
```

## 2. 当前边界

当前真正生效的登录边界请以这些文档为准：

- [frontend-backend-boundary.md](./frontend-backend-boundary.md)
- [api-response-standard.md](./api-response-standard.md)
- [../../black-tonny-frontend/docs/maintainers/login-evolution-handbook.md（workspace 链接）](../../black-tonny-frontend/docs/maintainers/login-evolution-handbook.md)

这意味着：

- 当前 `manifest/pages/dashboard summary/assistant chat` 这几条 runtime 接口仍不依赖 frontend bearer token
- 如果只是维护 dashboard、page payload、summary、assistant 主线，不需要顺手扩大 frontend bearer 鉴权范围
- `GET /api/dashboard/summary` 当前保持冻结，不因为 auth 主线回归而调整契约或依赖
- frontend 单仓开发仍可通过 `apps/backend-mock` 保留同路径 fallback，但 backend 仍是正式 auth source of truth

## 3. 当前约束

当前 backend frontend-auth 契约默认保持：

- 单店主优先，预留多角色扩展
- 继续兼容 frontend 当前 `vben` request/auth/router/store 主链
- 不绕开统一 auth provider 层
- 正式接口继续遵循 `{ code, data, message }`
- 不把 `/api/auth/refresh` 作为当前正式主线必需项

## 4. 非目标

本文件不承诺下面这些行为：

- 不要求 `manifest/pages/assistant` 当前挂上 frontend bearer 鉴权
- 不要求 `GET /api/dashboard/summary` 改变契约或鉴权范围
- 不要求 frontend 删除 `apps/backend-mock`
- 不要求 backend 这轮顺手扩展到完整生产级多角色体系
