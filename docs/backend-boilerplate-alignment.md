# Backend Boilerplate 对齐说明

## 1. 目的

这份文档定义 `black-tonny-backend` 后续开发时必须遵循的 backend 脚手架基线。

当前唯一基线是本地参考仓库：

- `FastAPI-boilerplate`

这里的“对齐”不是要求把当前仓库一次性重写成另一个项目，而是要求：

- 新的正式运行时结构必须按 boilerplate 的分层思想落位
- 当前已有的过渡实现必须被明确标成过渡态
- `research` / `page probe` / `UI 取证` 不能继续演化成正式架构骨架
- `capture` 必须优先稳定，不能因为研究代码扩张而失去清晰边界

如果需要看完整迁移顺序、分阶段目标和停靠点，请同时阅读 [backend boilerplate 彻底迁移路线图](./backend-boilerplate-migration-roadmap.md)。

## 2. 当前采用的 boilerplate 范围

本仓库后续只以 `FastAPI-boilerplate` 的 backend 结构作为脚手架基线。

本轮明确不采用其他仓库作为 backend 内部结构基线。

当前我们参考的 boilerplate 重点包括：

- `README.md`
- `docs/index.md`
- `docs/user-guide/project-structure.md`
- `docs/user-guide/development.md`
- `docs/user-guide/database/index.md`
- `docs/user-guide/testing.md`

从这些文档抽出的关键约束是：

1. 结构必须分层清楚
2. API 层保持薄
3. API 组织应允许 `api -> v1 -> routes` 这样的版本化结构演进
4. 数据模型、Schema、CRUD、核心配置、任务与中间件有明确落点
5. 正式运行时逻辑不能长期堆在一个平铺的大型 service 目录里

## 3. 对齐后的结构基线

后续 backend 正式结构以如下分层为准：

```text
app/
  api/
  core/
    db/
    exceptions/
    utils/
    worker/
  middleware/
  models/
  schemas/
  crud/
  services/
```

其中职责必须按下面理解：

### 3.1 `api/`

只负责：

- route 注册
- dependency 注入
- 请求参数接收
- 响应返回
- 调用下层能力

不负责：

- 直接承载业务真逻辑
- 直接拼接 `capture` / `serving` 查询细节
- 直接处理浏览器研究逻辑

### 3.2 `core/`

只负责跨模块公共底座：

- 配置
- 数据库连接
- 安全
- 日志
- 异常
- worker / queue
- 通用工具

`capture` 与 `serving` 的 engine / session / metadata 边界，也应归在这里的数据库底座能力里统一管理。

### 3.3 `models/`

只负责定义长期表结构与 ORM 模型。

后续应逐步把当前偏表结构/元数据性质的内容收口到这里，例如：

- capture 侧表
- serving 侧表
- 任务批次表
- 未来长期保留的业务投影表

### 3.4 `schemas/`

只负责：

- API 请求/响应 schema
- capture / serving 内部结构化数据 schema
- admission / analysis 结果的显式结构定义

不能把真实字段契约长期散落在 service 里隐式表达。

### 3.5 `crud/`

只负责数据库访问与持久化操作。

后续应逐步把下面这些职责从“大型 service”里拆出来：

- capture route 对应的原始写入
- capture batch 查询
- serving projection 读写
- 任务批次状态读写

原则是：

- 数据访问细节归 `crud`
- 业务编排归更上层

### 3.6 `middleware/`

只放运行时中间件，不放研究工具逻辑。

### 3.7 `services/`

保留，但角色必须被收窄成“编排层”，而不是默认的兜底目录。

后续 `services/` 只允许长期承担：

- 业务编排
- capture admission orchestration
- capture -> serving transform orchestration
- runtime 聚合协调

不应继续承担：

- 结构定义
- 表模型定义
- 持久化细节
- research 的全部事实来源

## 4. 当前仓库的过渡态判断

当前仓库和 boilerplate 最不一致的点有三类：

### 4.1 `app/services/` 过于平铺

当前大量内容都堆在：

- `app/services/*.py`

里面同时混合了：

- runtime service
- capture admission
- evidence analysis
- UI probe supporting logic
- 状态板 / registry 汇总

这会导致：

- 正式链和研究链边界模糊
- 模块职责漂移
- 后续迁移到稳定结构时成本越来越高

### 4.2 `models/` 与 `crud/` 缺位

当前仓库有：

- `app/db/`
- 平铺 `service`

但还没有把长期模型层和持久化层明确分成 boilerplate 风格的：

- `app/models/`
- `app/crud/`

这意味着很多正式数据边界仍然靠 service 文件隐式表达。

### 4.3 `research` 正在逼近正式骨架

当前已经有大量：

- evidence chain
- page research
- UI probe
- menu coverage audit
- maturity board / route registry

这些资产很有价值，但它们的职责是：

- 辅助识别
- 辅助准入
- 辅助定位 blocker

它们不应该继续主导正式 runtime / capture 的内部结构。

## 5. 当前对齐进度

当前已经完成的对齐动作有两类：

### 5.1 已冻结的正式边界

以下内容现在应视为稳定契约：

- `capture_batches`
- `capture_endpoint_payloads`
- capture batch status 集
- capture route registry 的必要字段
- admit / registry / batch lifecycle 的核心边界

这些边界后续可以迁移实现位置，但不应在迁移阶段随意改语义。

### 5.2 已建立的 boilerplate 目标目录

当前仓库已经建立以下目标目录骨架：

- `app/models/`
- `app/crud/`
- `app/middleware/`
- `app/services/runtime/`
- `app/services/capture/`
- `app/services/research/`
- `app/services/serving/`

这意味着后续新增正式代码已经不需要继续依赖 flat `app/services/` 作为唯一落点。

### 5.3 已切换的正式 capture 入口

当前已经完成第一批正式入口切换：

- `capture route registry`
  - 正式实现已迁到 `app/services/capture/route_registry.py`
  - `app/services/capture_route_registry_service.py` 只保留 `capture` 兼容壳
- `capture batch lifecycle`
  - 正式入口已迁到 `app/services/capture/batch_lifecycle.py`
- `capture admission orchestration`
  - 正式入口已开始迁到 `app/services/capture/admissions/`
- `capture persist helper`
  - 正式入口已开始迁到 `app/services/capture/persist_helpers.py`
- `maturity board`
  - 正式实现已迁到 `app/services/research/maturity_board.py`
  - 不再保留非 `capture` 所需的旧 flat `api_maturity_board_service.py`
- `page research / menu coverage audit`
  - `page research` 的正式实现已迁到 `app/services/research/page_research.py`
  - 不再保留非 `capture` 所需的旧 flat `yeusoft_page_research_service.py`
  - `menu coverage audit` 的正式实现已迁到 `app/services/research/menu_coverage.py`
  - 不再保留非 `capture` 所需的旧 flat `menu_coverage_audit_service.py`
- `retail detail stats`
  - 正式实现已迁到 `app/services/research/retail_detail_stats.py`
  - 不再保留非 `capture` 所需的旧 flat `retail_detail_stats_service.py`
- `customer/inventory/member/member maintenance evidence`
  - 正式实现已迁到 `app/services/research/`
  - 不再保留非 `capture` 所需的旧 flat `customer_evidence_service.py`
  - 不再保留非 `capture` 所需的旧 flat `inventory_evidence_service.py`
  - 不再保留非 `capture` 所需的旧 flat `member_evidence_service.py`
  - 不再保留非 `capture` 所需的旧 flat `member_maintenance_evidence_service.py`
- `receipt confirmation / return detail / store stocktaking evidence`
  - 正式实现已迁到 `app/services/research/`
  - 不再保留非 `capture` 所需的旧 flat `receipt_confirmation_evidence_service.py`
  - 不再保留非 `capture` 所需的旧 flat `return_detail_evidence_service.py`
  - 不再保留非 `capture` 所需的旧 flat `store_stocktaking_evidence_service.py`
- `stored value / daily payment / product sales snapshot / member sales rank snapshot evidence`
  - 正式实现已迁到 `app/services/research/`
  - 不再保留非 `capture` 所需的旧 flat `stored_value_evidence_service.py`
  - 不再保留非 `capture` 所需的旧 flat `daily_payment_snapshot_evidence_service.py`
  - 不再保留非 `capture` 所需的旧 flat `product_sales_snapshot_evidence_service.py`
  - 不再保留非 `capture` 所需的旧 flat `member_sales_rank_snapshot_evidence_service.py`
- `member analysis snapshot evidence`
  - 正式实现已迁到 `app/services/research/member_analysis_snapshot_evidence.py`
  - 不再保留非 `capture` 所需的旧 flat `member_analysis_snapshot_evidence_service.py`
- `product evidence`
  - 正式实现已迁到 `app/services/research/product_evidence.py`
  - 旧的 flat `product_evidence_service.py` 仅为 `capture` admit 兼容保留
- `runtime payload/status/homepage`
  - 正式入口已开始迁到 `app/services/runtime/`
  - `payload/homepage` 的正式实现已迁到 `app/services/runtime/`
- `runtime dashboard/jobs/cost snapshot`
  - 正式入口已开始迁到 `app/services/runtime/`
  - `status/dashboard/jobs/cost snapshot` 的正式实现已迁到 `app/services/runtime/`
- `runtime assistant/auth/user info`
  - 正式实现已迁到 `app/services/runtime/`
- `capture -> serving transform`
  - 正式实现已迁到 `app/services/serving/transform.py`
  - 不再保留非 `capture` 所需的旧 flat `capture_transform_service.py`
- `summary projection spec`
  - 正式实现已迁到 `app/services/serving/summary_projection.py`
  - 不再保留非 `capture` 所需的旧 flat `summary_projection_spec.py`
- 非 `capture` runtime 兼容壳
  - 已移除不再被正式路径使用的旧 flat runtime service 文件
  - 只在仍有正式调用依赖时才允许短期保留兼容壳
- `app/api/v1/`
  - 已建立内部组织层，用于对齐 boilerplate 风格
  - 当前仍保持外部 `/api/*` 契约，不提前引入 `/api/v1/*`
- `app/api/__init__.py`
  - 已成为正式顶层 router 装配入口
  - 旧的 `app/api/router.py` 不再保留为正式结构
- `capture -> serving transform`
  - 正式入口已开始迁到 `app/services/serving/`
- `capture batch / payload / analysis batch` 持久化
  - 已开始迁到 `app/crud/`
- `payload cache index / summary projection` 持久化
  - 已开始迁到 `app/crud/`
- `status` 运行时数据库诊断读查询
  - 已开始迁到 `app/crud/`
- `job run / job step` 读写
  - 已开始迁到 `app/crud/`
- `cost snapshot` 读写
  - 已开始迁到 `app/crud/`
- `dashboard summary` 的 serving 源数据读取
  - 已开始迁到 `app/crud/`
- admit / transform / fetch 等正式 capture 调用点
  - 已开始优先依赖新的 `app/services/capture/*` 入口
- board 重建与 research 入口
  - 已开始优先依赖新的 `app/services/research/*` 入口
- runtime 路由与 job 入口
  - 已开始优先依赖新的 `app/services/runtime/*` 入口

旧的 flat service 入口当前仍保留兼容，但它们现在应视为迁移兼容层，而不是长期首选入口。

## 6. 必须遵守的实施规则

从这份文档落地后，默认执行以下规则。

### 6.1 关于 `capture`

`capture` 是当前最优先要稳住的层。

因此：

- `capture_batches`
- `capture_endpoint_payloads`
- capture route registry
- capture admission batch 规则

都视为正式主线。

后续任何新增 route，如果已经进入正式 admit 路径，必须优先按 boilerplate 分层落位，不允许再把正式规则埋进 probe 或 evidence 代码里。

### 6.2 关于 `research`

研究链只服务于：

- 接口识别
- 参数确认
- 分页确认
- 隐藏上下文取证
- 准入决策

它不是正式架构真源。

允许保留 `research` 代码，但必须满足：

- 不定义正式 API 契约
- 不定义正式表结构
- 不定义长期持久化边界

### 6.3 关于新增代码

后续新增正式功能时，默认遵循：

1. 先定 `model`
2. 再定 `schema`
3. 再定 `crud`
4. 最后由 `service` 编排

如果当前阶段因为迁移还没完成，短期可以有兼容实现，但必须同时满足：

- 文档里明确写是过渡态
- 不把过渡态写成长期规则

### 6.4 关于 generated 文档

以下文档很重要，但它们不是内部架构真源：

- `docs/erp/api-maturity-board.md`
- `docs/erp/capture-route-registry.md`

它们回答的是：

- 当前路线状态
- 当前准入情况
- 当前 blocker

不回答：

- backend 内部结构如何设计
- 新代码该放在哪一层

这些问题以后统一以本文件和根架构文档为准。

## 6. 对 `capture` 主线的直接影响

如果要严格按 boilerplate 执行，后续对 `capture` 主线的影响是：

### 6.1 先冻结，再迁移

先冻结这些边界：

- capture 表结构
- capture route registry 字段
- admit artifact 命名
- batch 生命周期

冻结之后再迁移目录和职责，避免一边改结构一边改主线含义。

### 6.2 迁移顺序必须低风险

先迁：

- 文档规范
- 新目录
- import 兼容层

再迁：

- `models`
- `crud`
- capture orchestration

最后才迁：

- research 代码整理
- 长文件拆分

### 6.3 `serving` 仍然不能反压 `capture`

就算后面要继续整理结构，也不能为了服务 `serving` 或 dashboard，把 `capture` 重新做成“为页面服务的临时层”。

当前仍要坚持：

- `capture` 是原始层
- `serving` 是投影层

## 7. 推荐迁移顺序

低风险顺序如下：

1. 先把本文档加入正式读入口
2. 更新根文档，明确 boilerplate 是 backend 脚手架基线
3. 在代码层新增但暂不强制启用：
   - `app/models/`
   - `app/crud/`
   - `app/middleware/`
   - `app/services/capture/`
   - `app/services/research/`
4. 新增功能优先按新结构落位
5. 已有平铺 service 再按收益逐步迁移

## 8. 当前执行口径

从现在开始，当前仓库的执行口径是：

- backend 以 `FastAPI-boilerplate` 为唯一脚手架基线
- `capture` 主线优先稳定
- `research` 只能辅助，不得继续演化成正式架构真源
- 文档先对齐，代码后迁移

如果后续某份文档、脚本或讨论结论与这里冲突，以：

1. 根级标准文档
2. 本文档
3. 业务 working docs

这个顺序处理。
