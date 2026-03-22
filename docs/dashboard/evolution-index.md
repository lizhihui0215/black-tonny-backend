# Dashboard 演进索引

## 1. 这份索引的作用

backend 侧不重复维护完整的 Dashboard 演进叙事。

如果需要了解 Dashboard 主线已经演进到哪一步、当前边界是什么、下一步建议怎么推进，请优先阅读前端仓库中的主文档：

- [black-tonny-frontend/docs/dashboard/evolution-log.md（workspace 链接）](../../../black-tonny-frontend/docs/dashboard/evolution-log.md)

---

## 2. backend 自己的 source of truth

backend 侧只把以下两类文档作为自己的核心依据：

### 2.1 接口契约

- [docs/dashboard/summary-api.md](./summary-api.md)

用于定义：

- `/api/dashboard/summary` 的 query 参数
- 返回结构
- 字段说明
- 示例响应

### 2.2 数据架构

- [docs/two-database-architecture.md](../two-database-architecture.md)

用于定义：

- `black_tonny_capture`
- `black_tonny_serving`
- 批次流转
- capture 表到 serving 投影表的职责边界

这里的 `serving` 当前应理解为可演进的服务投影层，不是已经完全定型的最终标准库。

---

## 3. 使用建议

建议阅读顺序：

1. 先看前端主文档 [black-tonny-frontend/docs/dashboard/evolution-log.md（workspace 链接）](../../../black-tonny-frontend/docs/dashboard/evolution-log.md)
2. 再看 backend 的 [docs/dashboard/summary-api.md](./summary-api.md)
3. 再看 [docs/dashboard/summary-capture-mapping.md](./summary-capture-mapping.md)
4. 最后看 [docs/two-database-architecture.md](../two-database-architecture.md)

这样可以把：

- 产品主线
- 接口契约
- 当前 summary 抓取映射
- 数据架构

三层职责分开理解，避免在 backend 文档里重复维护同一份演进说明。
