# Backend Boilerplate 彻底迁移路线图

## 1. 目标

这份路线图定义 `black-tonny-backend` 如何从当前过渡态，彻底迁移到以 `FastAPI-boilerplate` 为底座的长期结构。

这里的“彻底迁移”不是指：

- 一次性重写全部代码
- 先推翻当前 `capture` 主线再重建

这里的“彻底迁移”指的是：

- backend 的长期目录与职责必须回到 boilerplate 风格
- `capture`、`serving`、runtime API、research 工具的结构边界必须明确
- 后续新增功能不能继续长在当前 flat service 过渡结构上
- 旧实现可以分批迁，但最终不能保留“以 research 为骨架”的临时架构

## 2. 迁移总原则

### 2.1 `capture` 优先稳定

迁移期间，`capture` 是第一优先级。

因此：

- 先冻结 `capture` 契约
- 再迁移目录
- 最后才拆大文件和去重逻辑

禁止为了“结构更干净”而打断：

- capture batch 写入
- route registry 生成
- 已准入路线的 admit 运行

### 2.2 research 只辅助，不主导结构

以下内容继续保留，但只能作为辅助层：

- page research
- menu coverage audit
- evidence chain
- UI probe
- maturity board
- capture route registry 的研究输入

它们帮助回答：

- 路线是否可信
- 参数是否已确认
- 是否可以准入 `capture`

但它们不能继续定义：

- backend 内部模块结构
- 正式持久化边界
- 长期 API / capture / serving 职责

### 2.3 迁移必须可停、可回滚、可兼容

每一阶段都必须满足：

- 旧路径还能跑
- 新路径开始承接新功能
- 切换后可通过 import 兼容或 wrapper 回退

不能做“半天内全量搬家”的高风险操作。

## 3. 当前迁移进度

当前执行状态已经进入“先稳 `capture`，再迁结构”的正式阶段。

### 3.1 已完成

- `Phase 0` 已完成
  - `capture_batches`
  - `capture_endpoint_payloads`
  - capture batch status 集合
  - route registry 必要字段
  - admit / registry / batch lifecycle 的核心边界
  已经被显式收口成可校验契约
- `Phase 1` 已完成
  - 已建立：
    - `app/models/`
    - `app/crud/`
    - `app/middleware/`
    - `app/services/runtime/`
    - `app/services/capture/`
    - `app/services/research/`
    - `app/services/serving/`
  - 当前这些目录已经是正式目标落点
- `capture` 主线保持稳定
  - 当前已准入与已写入的 `capture` 路线未因结构收口而回退
  - admit、registry、board、batch lifecycle 仍可运行

### 3.2 进行中

- `Phase 2` 已开始执行
  - 新增正式 `capture` 代码，默认应优先进入 `app/services/capture/`
  - 新增 research / probe / evidence 代码，默认应优先进入 `app/services/research/`
  - flat `app/services/` 仍保留兼容，但不再是长期正式目标
- `Phase 3` 的第一小步已开始落地
  - `capture route registry` 的正式实现已迁到 `app/services/capture/route_registry.py`
  - `app/services/capture_route_registry_service.py` 只保留 `capture` 兼容壳
  - `capture batch lifecycle` 的正式调用入口已切到 `app/services/capture/batch_lifecycle.py`
  - `capture admission orchestration` 的正式入口已开始切到 `app/services/capture/admissions/`
  - `capture persist helper` 的正式入口已开始切到 `app/services/capture/persist_helpers.py`
  - `maturity board` 的正式研究实现已迁到 `app/services/research/maturity_board.py`
  - 不再保留非 `capture` 所需的旧 flat `api_maturity_board_service.py`
  - `page research / menu coverage audit` 的正式研究实现已迁到 `app/services/research/`
  - `retail detail stats` 的正式研究实现已迁到 `app/services/research/retail_detail_stats.py`
  - `customer/inventory/member/member maintenance evidence` 的正式研究实现已迁到 `app/services/research/`
  - `receipt confirmation / return detail / store stocktaking evidence` 的正式研究实现已迁到 `app/services/research/`
  - `stored value / daily payment / product sales snapshot / member sales rank snapshot evidence` 的正式研究实现已迁到 `app/services/research/`
  - `member analysis snapshot evidence` 的正式研究实现已迁到 `app/services/research/member_analysis_snapshot_evidence.py`
  - `product evidence` 的正式研究实现已迁到 `app/services/research/product_evidence.py`
  - 旧的 flat `product_evidence_service.py` 仅为 `capture` admit 兼容保留
  - 不再保留非 `capture` 所需的旧 flat `yeusoft_page_research_service.py`
  - 不再保留非 `capture` 所需的旧 flat `menu_coverage_audit_service.py`
  - 不再保留非 `capture` 所需的旧 flat `retail_detail_stats_service.py`
  - 不再保留非 `capture` 所需的旧 flat `customer_evidence_service.py`
  - 不再保留非 `capture` 所需的旧 flat `inventory_evidence_service.py`
  - 不再保留非 `capture` 所需的旧 flat `member_evidence_service.py`
  - 不再保留非 `capture` 所需的旧 flat `member_maintenance_evidence_service.py`
  - 不再保留非 `capture` 所需的旧 flat `receipt_confirmation_evidence_service.py`
  - 不再保留非 `capture` 所需的旧 flat `return_detail_evidence_service.py`
  - 不再保留非 `capture` 所需的旧 flat `store_stocktaking_evidence_service.py`
  - 不再保留非 `capture` 所需的旧 flat `stored_value_evidence_service.py`
  - 不再保留非 `capture` 所需的旧 flat `daily_payment_snapshot_evidence_service.py`
  - 不再保留非 `capture` 所需的旧 flat `product_sales_snapshot_evidence_service.py`
  - 不再保留非 `capture` 所需的旧 flat `member_sales_rank_snapshot_evidence_service.py`
  - 不再保留非 `capture` 所需的旧 flat `member_analysis_snapshot_evidence_service.py`
  - `payload/status/homepage` 的正式 runtime 入口已开始切到 `app/services/runtime/`
  - `dashboard/jobs/cost snapshot` 的正式 runtime 入口已开始切到 `app/services/runtime/`
  - `status/dashboard/jobs/cost snapshot` 的正式实现已迁到 `app/services/runtime/`
  - `payload/homepage` 的正式实现已迁到 `app/services/runtime/`
  - `assistant/auth/user info` 的正式实现已迁到 `app/services/runtime/`
  - 旧的 flat `*_service.py` 现在只保留兼容壳，不再作为正式实现
  - `api -> v1 -> routes` 的内部组织层已建立，顶层 router 装配已迁到 `app/api/__init__.py`，但仍保持外部 `/api/*` 契约不变
  - `capture -> serving transform` 的正式实现已迁到 `app/services/serving/transform.py`
  - `summary projection spec` 的正式实现已迁到 `app/services/serving/summary_projection.py`
  - 不再保留非 `capture` 所需的旧 flat `capture_transform_service.py`
  - 不再保留非 `capture` 所需的旧 flat `summary_projection_spec.py`
  - 不再保留非 `capture` 所需的旧 flat runtime service 文件
  - 不再保留非 `capture` 所需的旧 flat `assistant_service.py`
  - 不再保留非 `capture` 所需的旧 flat `auth_service.py`
  - `capture batch / payload / analysis batch` 的底层持久化已开始切到 `app/crud/`
  - `payload cache index` 与 `summary projection` 的底层持久化已开始切到 `app/crud/`
  - `status` 运行时数据库诊断读查询已开始切到 `app/crud/`
  - `job run / job step` 的底层读写已开始切到 `app/crud/`
  - `cost snapshot` 的底层读写已开始切到 `app/crud/`
  - `dashboard summary` 的 serving 源数据读取已开始切到 `app/crud/`
  - admit / transform / fetch 脚本与正式 capture admission service 已开始优先依赖新入口

### 3.3 下一步

- 继续推进 `Phase 3`
  - 继续迁：
    - research 正式入口与 board 重建入口
    - runtime 正式入口与 payload/status 兼容桥接
    - analysis board / registry 的正式重建主链依赖
    - 旧 flat service 到新 capture 入口的剩余兼容桥接清单
  - 保留旧 import 兼容，避免打断当前 `capture` 主线

### 3.4 当前执行规则

从现在开始，迁移判断以这份路线图为准：

- 先判断代码是不是正式 `capture`
- 如果是，优先落到 `app/services/capture/`
- 如果只是 evidence / probe / page research，则落到 `app/services/research/`
- 若因为兼容暂时仍在 flat `app/services/`，必须视为过渡态，而不是长期结构

## 4. 目标结构

最终目标结构以 boilerplate 思路为准：

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
    runtime/
    capture/
    research/
    serving/
```

### 4.1 长期职责

- `api/`
  - 路由与依赖
- `core/`
  - 配置、数据库底座、安全、日志、公共异常、worker
- `models/`
  - 长期表结构
- `schemas/`
  - API 契约与内部结构化 schema
- `crud/`
  - 数据访问层
- `services/runtime/`
  - manifest/pages/dashboard/assistant/status/jobs 等正式运行时编排
- `services/capture/`
  - route registry、admission、persist、capture batch orchestration
- `services/research/`
  - evidence、page research、probe、maturity board 输入
- `services/serving/`
  - capture -> serving transform 与 serving projection 编排

## 5. 当前过渡态问题

当前必须被迁出的主要问题有：

### 5.1 `app/services/` 平铺过重

当前 flat service 目录里混合了：

- runtime service
- capture admit
- evidence chain
- board / registry
- UI probe supporting logic

这会导致：

- 正式主线与研究链耦合
- 新人很难判断代码该放哪里
- 后续长期维护成本越来越高

### 5.2 `models/` 与 `crud/` 长期缺位

当前很多长期边界仍然靠：

- `app/db/`
- `app/services/*`

隐式表达。

这与 boilerplate 的长期结构不一致。

### 5.3 研究产物影响了正式结构判断

虽然当前状态板和 registry 很有价值，但它们已经太容易被误读成：

- “这就是后端结构”
- “新 route 就继续按这个方式堆 service”

这个趋势必须停止。

## 6. 迁移阶段

### Phase 0：冻结契约 `已完成`

先冻结这些正式边界：

- `capture_batches`
- `capture_endpoint_payloads`
- `capture route registry` 字段
- admit artifact 命名
- capture batch 生命周期
- serving 当前读取边界

验收标准：

- 当前已写入 `capture` 的路线行为不变
- 状态板与 registry 仍能重建

### Phase 1：建立新目录，不迁行为 `已完成`

先创建并接入空目录：

- `app/models/`
- `app/crud/`
- `app/middleware/`
- `app/services/runtime/`
- `app/services/capture/`
- `app/services/research/`
- `app/services/serving/`

当前 flat 目录仍保留。

验收标准：

- 新目录已成为允许新增代码的正式落点
- 旧逻辑不受影响

### Phase 2：新增代码只进新结构 `进行中`

从这一阶段开始：

- 新增正式 `capture` 逻辑只允许写到 `services/capture/`
- 新增 probe/evidence 只允许写到 `services/research/`
- 新增 runtime 编排只允许写到 `services/runtime/`

禁止再往 flat `app/services/` 添加新的长期正式模块。

验收标准：

- 新提交的结构方向开始稳定
- 不再继续制造新的迁移债务

### Phase 3：迁移 `capture` 正式主线 `下一阶段`

优先迁移：

- route registry
- capture admission orchestration
- capture persist helpers
- batch lifecycle

迁移方式：

- 先拷贝到新位置
- 旧路径保留兼容导出
- tests 全部回归通过后再逐步移除旧入口

验收标准：

- `capture` 主线可以在新结构下稳定运行
- admit 脚本、registry、状态板不回退

### Phase 4：迁移 `research`

迁移：

- evidence chain service
- page research service
- menu coverage audit
- probe supporting logic

原则：

- research 迁移优先保证边界清晰
- 不急于统一成一个“万能 service”

验收标准：

- research 和 capture 目录职责明确
- 新人能一眼看出“这是正式链还是研究链”

### Phase 5：补 `models / schemas / crud`

把长期正式结构逐步显式化：

- capture 侧长期模型
- serving 侧长期模型
- admit / analysis 结构 schema
- capture / serving 读写 crud

这一步才是真正从“service 驱动”转回“boilerplate 驱动”。

验收标准：

- 长期边界不再依赖 flat service 隐式表达
- 关键持久化逻辑开始收敛到 `crud`

### Phase 6：清理兼容层

当前面阶段稳定后，再逐步清理：

- flat `app/services/` 里的旧入口
- 不再需要的 wrapper
- 只用于过渡的导入桥接

验收标准：

- 新结构成为唯一主路径
- 旧结构只保留必要兼容，或完全移除

## 7. 具体迁移优先级

### 第一优先级

这些必须先迁：

- capture route registry
- sales / inventory / member / product 的 admit orchestration
- capture persist helper
- analysis board 重建主链

### 第二优先级

- evidence chain service
- page research service
- menu coverage audit
- UI probe supporting logic

### 第三优先级

- 大型历史 service 拆分
- 目录清理
- 命名统一

## 8. 明确不做的事

在彻底迁移过程中，以下事情默认不做：

- 不改公开 API 契约
- 不为了重构先改 `dashboard` / `assistant` 行为
- 不让 `serving` 反向驱动 `capture`
- 不一次性重命名所有 artifact
- 不用“大统一 mega-service”替代当前 flat service 问题

## 9. 对当前主线的直接要求

在彻底迁移完成前，主线程执行时必须遵守：

1. 新的正式 admit / persist 代码优先按目标结构写
2. 新的 probe / evidence 代码优先按 research 结构写
3. 若暂时还没迁目录，必须在实现和文档里标明这是过渡态
4. 每次结构迁移都要保证：
   - 状态板可重建
   - registry 可重建
   - 已准入 route 可继续写入 capture

## 10. 迁移完成的判定标准

满足以下条件时，视为“彻底迁移完成”：

- backend 正式新增代码已经不再依赖 flat `app/services/`
- capture 主线正式逻辑已经收口到 boilerplate 风格结构
- research 代码明确只作为辅助层
- models / schemas / crud / orchestration 的长期职责已经清晰
- 文档入口、架构入口、数据边界入口已经全部一致

## 11. 当前执行口径

从这份路线图开始，当前执行口径固定为：

- 先稳住 `capture`
- 再按 boilerplate 风格彻底迁移
- 研究链继续保留，但不再主导 backend 长期结构
