# Dashboard Summary v0 抓取映射草案

## 1. 这份文档的定位

这份文档只服务当前 Dashboard 顶部 8 张卡主线。

它定义的是：

- 当前 `capture -> serving -> /api/dashboard/summary` 这条链路需要哪些原始 endpoint
- 每个 endpoint 至少要提供哪些字段
- 这些字段当前如何投影到 serving 层

它**不是**最终数仓设计，也**不是**长期标准模型说明。

当前约定继续保持：

- `capture` 是更稳定的原始数据留存层
- `serving` 是面向当前页面/API 的 v0 投影层
- summary API 契约比 serving 表结构更稳定
- `零售明细统计` 当前只作为销售域补充/对账路线，不直接进入顶部 8 张卡主链
- `销售清单` 当前已确认存在“按单据”和“按明细”两种粒度路线，后续必须先做头行关系确认，不能直接混接进同一层投影
- 当前最新证据闭环已经确认：
  - `SelSaleReport` 是订单头候选源
  - `GetDIYReportData(gridid=_2)` 是明细行候选源
  - `sale_no / 零售单号` 是当前最稳定的头行关联键
  - 但 `sale_date / operator` 仍不稳定，因此本轮仍不把销售明细路线直接接进 summary 主链

---

## 2. 当前主线需要的 4 个 capture endpoint

为了支撑 Dashboard 顶部 8 张卡，当前 transform 最少需要以下 4 类 endpoint：

1. `sales_orders`
2. `sales_order_items`
3. `inventory_current`
4. `inventory_daily_snapshot`

一个 `capture_batch_id` 要能完成当前 summary 投影，建议这 4 类 endpoint 都存在。

注意：

- endpoint 可以返回空数组
- 但 endpoint 本身应该存在
- 如果真实上游命名不同，优先在 transform 层做映射，不要急着改 serving 表结构

---

## 3. endpoint -> serving 投影关系

| capture endpoint | 当前 serving 投影表 | 作用 |
|---|---|---|
| `sales_orders` | `sales_orders` | 销售额、订单数、客单价 |
| `sales_order_items` | `sales_order_items` | 销售件数、连带率 |
| `inventory_current` | `inventory_current` | 低库存、缺码、过季库存当前值 |
| `inventory_daily_snapshot` | `inventory_daily_snapshot` | 库存风险类卡片对比周期变化 |

---

## 4. 字段草案

### 4.1 `sales_orders`

目标表：`sales_orders`

必填字段：

- `order_id`
- `paid_at`
- `paid_amount`

可选字段：

- `store_id`
- `payment_status`
- `created_at`
- `updated_at`

当前说明：

- `payment_status` 未传时默认按 `paid` 处理
- 当前 summary 只统计已支付订单
- 如果真实接口字段名不是这套 canonical 名称，应在 transform 层做字段映射

### 4.2 `sales_order_items`

目标表：`sales_order_items`

必填字段：

- `order_id`
- `sku_id`
- `quantity`

可选字段：

- `style_code`
- `color_code`
- `size_code`
- `created_at`
- `updated_at`

当前说明：

- `order_id` 用于与订单头数据关联
- `quantity` 用于计算销售件数和连带率

### 4.3 `inventory_current`

目标表：`inventory_current`

必填字段：

- `sku_id`
- `on_hand_qty`
- `safe_stock_qty`

可选字段：

- `store_id`
- `style_code`
- `color_code`
- `size_code`
- `season_tag`
- `is_all_season`
- `is_target_size`
- `is_active_sale`
- `updated_at`

当前说明：

- `on_hand_qty <= safe_stock_qty` 用于判定低库存
- `style_code + color_code + target_size` 用于缺码款判断
- `season_tag + is_all_season` 用于过季库存判断

### 4.4 `inventory_daily_snapshot`

目标表：`inventory_daily_snapshot`

必填字段：

- `snapshot_date`
- `sku_id`
- `on_hand_qty`
- `safe_stock_qty`

可选字段：

- `store_id`
- `style_code`
- `color_code`
- `size_code`
- `season_tag`
- `is_all_season`
- `is_target_size`
- `is_active_sale`
- `created_at`

当前说明：

- 当前 summary 使用“对比区间结束日”的日快照，计算库存风险类卡片的变化值
- 如果后续验证发现仅用结束日快照不够，再升级这一层规则，但先不扩散表结构

---

## 5. 当前 transform 约定

当前 transform 入口：

- 服务：`app/services/serving/transform.py`
- 脚本：`scripts/transform_capture_batch.py`

当前行为：

1. 从 `capture_batches` 和 `capture_endpoint_payloads` 读取一个 `capture_batch_id`
2. 找到当前 summary 所需的 4 类 endpoint
3. 做最小字段校验与类型归一
4. 写入 serving v0 投影表
5. 写入 / 更新 `analysis_batches`
6. 回写 capture batch 的 `transformed` 状态

### 5.1 当前已支持常见字段别名

由于真实上游接口字段名还未最终锁定，当前 transform 已支持一层“canonical 字段 + 常见别名”的归一策略。

例如：

- `order_id` 也可接受 `orderNo` / `trade_no`
- `paid_at` 也可接受 `pay_time` / `payment_time`
- `paid_amount` 也可接受 `actual_amount` / `payAmount`
- `sku_id` 也可接受 `skuCode`
- `quantity` 也可接受 `qty`
- `on_hand_qty` 也可接受 `stockQty` / `current_stock`
- `safe_stock_qty` 也可接受 `alarmStock` / `warn_stock`
- `snapshot_date` 也可接受 `bizDate` / `stat_date`

当前策略是：

- 先优先使用 canonical 字段名
- 没有 canonical 字段时，再尝试常见别名
- 如果 canonical 和别名都没有，再判定为缺字段

这层 alias 归一是为了让我们先接真实样本验证 summary 主线，不是为了在当前阶段冻结最终字段体系。

当前不会做的事：

- 不把 serving 解释成最终标准库
- 不为了某个真实接口的字段怪异，立刻改全局表结构
- 不在这份文档里承诺完整抓取体系已经定型

---

## 6. 建议的真实抓取接入顺序

### 第一步：确认真实 endpoint 名称与分页方式

先搞清楚上游真实接口中：

- 哪个接口对应订单头
- 哪个接口对应订单明细
- 哪个接口对应当前库存
- 哪个接口对应库存快照

当前销售域尤其要先收口这条边界：

- `menuid=E004001008, gridid=_1`
  - 更偏“按单据”
  - 值得作为订单头候选源研究
- `menuid=E004001008, gridid=_2`
  - 更偏“按明细”
  - 值得作为订单行候选源研究
- `SelSaleReport`
  - 当前也更像单据级汇总/查询路线

当前最新研究更进一步确认：

- `_1` 的 grid 定义和 `SelSaleReport` 返回字段都集中在：
  - `SaleNum`
  - `SaleDate`
  - `TotalSaleAmount`
  - `TotalSaleMoney`
  - `ReceiveMoney`
- `_2` 的 grid 定义集中在：
  - `零售单号`
  - `明细流水`
  - `款号`
  - `颜色`
  - `尺码`
  - `数量`
  - `金额`

所以对 summary 主线来说，当前更合理的方向是：

- 订单头候选优先看 `_1 / SelSaleReport`
- 订单行候选优先看 `_2 / 销售清单`
- 在 `SaleNum / 零售单号` 的头行关系没坐实前，不把两条路线强行并成同一张投影表

第二轮页面级单变量深挖进一步确认：

- `SelSaleReport` 与 `GetDIYReportData(gridid=_2)` 当前必须继续拆成两条路线
- `parameter.Tiem=0/1/2` 在当前账号样本下没有切出新的数据集，不构成 8 张卡主链必须 sweep 的条件
- `零售明细统计` 当前仍维持“研究/对账源”定位，不提前接入 `sales_orders / sales_order_items` 主链

如果不先把这三条路线的粒度关系搞清楚，后续很容易出现：

- 订单数重复
- 销售金额双计
- 客单价失真
- 件数与连带率口径错位

### 第二步：拿真实 payload 做字段映射

把真实字段映射到这份草案里的 canonical 字段，再决定 transform 层别名怎么写。

### 第三步：只验证 summary 主线

优先验证 8 张卡是否算对：

- 销售额
- 订单数
- 客单价
- 销售件数
- 连带率
- 低库存 SKU 数
- 缺码款数
- 过季库存件数

### 第四步：再决定是否升级 serving 投影

如果后续趋势图、库存风险明细、热销商品等模块需要更多字段，再逐步扩 serving。

不是现在一次把所有长期结构设计完。
