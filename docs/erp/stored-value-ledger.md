# 储值域接口台账

## 1. 当前目标

储值域当前重点是：

- 区分门店级汇总、卡级汇总、卡级明细三层接口
- 避免把汇总接口误当作明细源
- 明确搜索条件和时间范围的真实含义

---

## 2. 接口总表

| 页面/报表 | endpoint | method | 认证方式 | 主要过滤字段 | 当前判断 | 风险标签 | 抓取策略 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 储值按店汇总 | `FXDIYReport/GetDIYReportData` | `POST` | `token` | `menuid` `gridid` `parameter.BeginDate` `EndDate` | 门店级汇总接口 | 只能当结果快照 | 结果快照 |
| 储值卡汇总 | `FXDIYReport/GetDIYReportData` | `POST` | `token` | `menuid` `gridid` `parameter.BeginDate` `EndDate` `Search` | 卡级汇总接口 | 只能当结果快照 | 结果快照 |
| 储值卡明细 | `FXDIYReport/GetDIYReportData` | `POST` | `token` | `menuid` `gridid` `parameter.BeginDate` `EndDate` `Search` | 当前最像储值流水明细候选 | 需要扫枚举 | 单请求 |

---

## 3. 关键过滤条件分析

储值域当前全部走 `FXDIYReport/GetDIYReportData`，因此存在共同风险：

- 强依赖 `menuid`
- 强依赖 `gridid`
- `parameter` 是页面语义的一部分，不只是业务筛选

当前已知筛选字段主要有：

- `BeginDate`
- `EndDate`
- `Search`

当前已确认：

- `Search=""` 会返回当前主集合
- `Search` 对卡号类值可以显著收窄集合
- `BeginDate/EndDate` 会显著收窄集合
- `BeginDate/EndDate` 当前更像半开区间 `[BeginDate, EndDate)`，用季度半开分片后并集可以与 baseline 对齐
- `储值卡汇总` 当前更像单请求卡级快照，`page/pagesize` 对已测值不改变结果集
- `储值按店汇总` 当前更像单请求门店级快照，`page/pagesize` 对已测值不改变结果集

当前还不能证明：

- `Search` 对单据号或姓名的搜索语义
- 不同 `menuid/gridid` 是否只是视图差异，还是彻底不同数据集

当前最新判断：

- `储值卡明细` 已具备按默认空 `Search` 单请求进入 `capture` 的条件
- `Search` 当前只建议作为卡号类过滤器使用，不建议把 `HappenNo / VipName` 当成稳定搜索键
- `储值卡汇总` 已具备按默认空 `Search` 单请求进入 `snapshot capture` 的条件
- `储值按店汇总` 已具备按默认时间窗单请求进入 `snapshot capture` 的条件

---

## 4. 维度重叠与失真风险

储值域当前天然分成三层：

- 门店级汇总
- 卡级汇总
- 卡级明细

当前规则：

- `储值卡明细` 可以作为明细候选
- `储值按店汇总` 与 `储值卡汇总` 只做快照、对账和聚合校验

不允许把三者混算成同一种“储值事实表”。

---

## 5. 金额字段现状

储值域是金额字段很丰富的区域，但当前重点不是成本字段，而是：

- 充值金额
- 消费金额
- 余额
- 期初/期末余额

当前尚未发现储值域与商品成本直接相关的字段。

---

## 6. 当前建议

- 主源候选：`储值卡明细`
- 快照候选：`储值按店汇总`、`储值卡汇总`

---

## 7. 后续待验证事项

1. `储值卡明细.Search` 的搜索语义
2. `储值卡明细` 是否存在隐藏分页或分页上限
3. `Search` 是否只对 `VipCardId` 生效，还是还能匹配 `HappenNo` / `VipName`
4. `FXDIYReport` 在储值域是否还存在其他 `menuid/gridid` 变体
