# 工具文档入口

这组文档只负责 `black-tonny-backend` 仓库内的工具使用说明。

它们回答的是：

- MCP 在这个仓库里的定位是什么
- Playwright / 浏览器研究链该怎么用
- 哪些脚本是研究辅助，哪些是正式抓取主链

当前仓库的默认原则是：

- 正式规则写在仓库文档里
- `AGENTS / CLAUDE / GEMINI` 只负责导航和读顺序
- skills 如果存在，也只保留为薄适配层或工具型辅助
- 如果某个 skill 不再明显节省重复沟通或工具接线成本，就不应继续重点维护
- backend 正式结构以 [backend boilerplate 对齐说明](../backend-boilerplate-alignment.md) 为准，彻底迁移顺序以 [backend boilerplate 彻底迁移路线图](../backend-boilerplate-migration-roadmap.md) 为准，tooling 文档不能反向定义长期架构

它们不回答业务口径，也不替代 ERP / dashboard 的业务文档。

## 适用范围

- AI 会话辅助工具
- 浏览器研究工具
- repo-local 研究脚本入口
- 文档读入口与使用边界

不适用范围：

- `capture` / `serving` 业务口径
- API 契约
- dashboard 指标定义

这些内容继续以业务文档为准：

- [ERP 接口研究总览](../erp/README.md)
- [ERP API 成熟度总览](../erp/api-maturity-board.md)
- [ERP Capture 全量导入路线图](../erp/capture-ingestion-roadmap.md)
- [dashboard summary API 契约](../dashboard/summary-api.md)

## 文档列表

- [MCP 使用说明](./mcp-guide.md)
  - MCP 的用途、配置位置、调用方式、权限边界和常见问题
- [浏览器研究工具说明](./browser-research-tools.md)
  - Playwright profile、研究 runner、产物目录、推荐命令和使用边界
- [AI 协作低 Token 操作手册](./ai-token-playbook.md)
  - AI 协作场景下的最小读法、搜索约束、事实缓存模板和降耗建议

## 低 Token 协作入口

- 先看 [../../AGENTS.md](../../AGENTS.md) 里的 task routing，判断本次任务的 minimum read set。
- 如果问题本身就是 AI 协作成本、搜索范围或文档读法，继续看 [AI 协作低 Token 操作手册](./ai-token-playbook.md)。
- 只有当任务真正触达业务契约、数据边界或主链准入时，再回到对应业务文档扩读。
- 低 Token 协作规则只在这份入口和 [AI 协作低 Token 操作手册](./ai-token-playbook.md) 收口，不向其他业务 area docs 扩散同类操作说明。

## 读法建议

1. 先看这份入口，确认你是在找“业务文档”还是“工具文档”
2. 如果任务涉及 AI 协作 token、读法优化或工具搜索范围，先走低 Token 协作入口
3. 如果任务涉及 MCP、Playwright、profile、研究脚本，继续看这里的 tooling docs
4. 如果任务涉及指标口径、接口可信度、主链准入，回到 ERP / dashboard 业务文档

## 当前边界

- MCP、Playwright 和浏览器研究链都只是开发与研究辅助
- 它们不是 backend 运行时依赖，也不是正式抓取主链
- 正式抓取与正式入库仍然以纯 HTTP 和业务准入规则为准
- 研究脚本与 probe 结果可以影响准入判断，但不能成为 backend 内部结构的真源
- 不允许把 backend 规则只写在 adapter 或某个 skill 里而不落仓库文档
