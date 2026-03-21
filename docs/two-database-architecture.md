# 两库架构说明

## 目标

`black-tonny-backend` 现在只保留两类长期数据库：

- `black_tonny_capture`
- `black_tonny_serving`

业务接口只读取 `black_tonny_serving`；采集镜像、分页回放、原始 payload 审计只写 `black_tonny_capture`。

需要特别说明的是：

- `capture` 是当前更稳定的原始数据层
- `serving` 不是已经定型的“最终标准库”
- `serving` 当前应理解为面向页面和 API 的可演进投影层

也就是说，这份文档定义的是当前两库职责边界，不是承诺所有 serving 表结构都已经最终定稿。

## 数据流

1. 上游抓取接口返回分页 payload
2. 原始 payload 先写入 `black_tonny_capture`
3. 按 `capture_batch_id` 触发转换
4. 当前页面/API 需要的投影表写入 `black_tonny_serving`
5. FastAPI 页面接口和 Dashboard API 只读 `black_tonny_serving`

## 环境变量

- `CAPTURE_DB_URL`
- `SERVING_DB_URL`

`APP_DB_URL` 和 `ANALYSIS_DB_URL` 目前只保留为兼容回退，不再作为目标架构命名。

## Capture 库

按源接口建表，重点是可回放、可审计、可排错。

### `capture_batches`

- `capture_batch_id`
- `batch_status`
- `source_name`
- `pulled_at`
- `transformed_at`
- `created_at`
- `updated_at`
- `error_message`

### `capture_endpoint_payloads`

- `capture_batch_id`
- `source_endpoint`
- `page_cursor`
- `page_no`
- `request_params`
- `payload_json`
- `checksum`
- `pulled_at`
- `created_at`

## Serving 库

同时承载应用运行表和业务服务投影表。

当前推荐把它理解为：

- 面向现阶段页面和 API 的服务层数据库
- 可以随着业务理解、抓取字段和分析口径逐步调整
- 先服务当前模块，再决定哪些结构值得沉淀成长期标准模型

不建议在这个阶段把 serving 里的所有表都当作最终稳定模型。

### 应用运行表

- `job_runs`
- `job_steps`
- `cost_snapshots`
- `payload_cache_index`

### 批次表

- `analysis_batches`
  - `analysis_batch_id`
  - `capture_batch_id`
  - `batch_status`
  - `source_endpoint`
  - `pulled_at`
  - `transformed_at`

### Dashboard Summary 首批 v0 投影表

- `sales_orders`
- `sales_order_items`
- `inventory_current`
- `inventory_daily_snapshot`

这些表当前主要用于支撑 Dashboard 顶部 8 张卡。

它们的定位是：

- 已经可用
- 足以支撑当前 summary 主线
- 但仍然允许后续随着真实数据和业务理解继续演进

## Dashboard 顶部 8 卡的数据落点

### 时间累计型

- `salesAmount`
- `orderCount`
- `avgOrderValue`
- `salesQuantity`
- `attachRate`

来源：

- `sales_orders`
- `sales_order_items`

### 当前状态型

- `lowStockSkuCount`
- `sizeBreakStyleCount`
- `outOfSeasonStockQty`

来源：

- 当前值：`inventory_current`
- 周期变化：`inventory_daily_snapshot`

## 服务边界

- `get_capture_engine()`
  - 仅供采集任务、原始 payload 落库、转换任务使用
- `get_serving_engine()`
  - 供 FastAPI 业务接口、状态页、任务表、缓存索引、当前业务投影表使用

禁止业务接口直接读 `capture` 表。

## 当前实现状态

- 两套 engine 和 metadata 已拆分
- Docker Compose 会初始化 `black_tonny_capture` 与 `black_tonny_serving`
- `/api/dashboard/summary` 契约已经固定，当前支持“优先读 serving，缺数据再回退 sample/cache”
- capture 到 serving 的最小转换闭环已经存在，但 serving 仍然是 v0 投影层
- 后续接真实抓取时，先写 `capture`，再按当前模块需要转换到 `serving`
