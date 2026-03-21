# 库存域接口台账

## 1. 当前目标

库存域的研究重点是：

- 哪些接口更适合作为库存事实源
- 哪些接口只是库存分析视图
- `rtype/type/stockflag` 等视图参数到底是切视图还是切数据子集
- 当前是否存在成本金额、库存金额与零售价金额混淆的风险

---

## 2. 接口总表

| 页面/报表 | endpoint | method | 认证方式 | 主要过滤字段 | 当前判断 | 风险标签 | 抓取策略 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 库存明细统计 | `YisEposReport/SelDeptStockWaitList` | `POST` | `token` | `bdate` `edate` `depts` `spenum` `warecause` `stockflag` `page` `pagesize` | 当前最像库存事实源候选 | 需要翻页 | 自动翻页 |
| 库存零售统计 | `YisEposReport/SelDeptStockSaleList` | `POST` | `token` | `bdate` `edate` `depts` `spenum` `warecause` `page` `pagesize` | 更像库存结果视图，字段偏零售统计 | 需要翻页 | 结果快照 |
| 库存总和分析-按年份季节 | `YisEposReport/SelStockAnalysisList` | `POST` | `token` | `rtype=1` `spenum` `warecause` | 视图接口，不宜直接当明细源 | 需要扫枚举 | 结果快照 |
| 库存总和分析-按中分类 | `YisEposReport/SelStockAnalysisList` | `POST` | `token` | `rtype=2` `spenum` `warecause` | 同上，当前仍待完整确认 | 需要扫枚举 | 结果快照 |
| 库存总和分析-按波段 | `YisEposReport/SelStockAnalysisList` | `POST` | `token` | `rtype=3` `spenum` `warecause` | 同上，当前仍待完整确认 | 需要扫枚举 | 结果快照 |
| 库存多维分析 | `YisEposReport/SelDeptStockAnalysis` | `POST` | `token` | `bdate` `edate` `warecause` `spenum` `depts` `stockflag` `page` `pagesize` | 高价值分析接口，但更像宽表结果 | 需要翻页 | 结果快照 |
| 进销存统计 | `YisEposReport/SelInSalesReport` | `POST` | `token` | `bdate` `edate` `sort` `spenum` `warecause` `page` `pagesize` | 进销存结果接口，适合对账 | 需要翻页 | 结果快照 |
| 日进销存 | `YisEposReport/SelInSalesReportByDay` | `POST` | `token` | `bdate` `edate` `warecause` `spenum` `page` `pagesize` | 日级快照接口 | 需要翻页 | 结果快照 |
| 出入库单据 | `YisEposReport/SelOutInStockReport` | `POST` | `token` | `bdate` `edate` `datetype` `type` `doctype` `spenum` `warecause` `page` `pagesize` | 准明细单据源候选 | 需要扫枚举 | 自动翻页 |

---

## 3. 关键过滤条件分析

### 3.1 分页风险

库存域已确认存在多种分页写法：

- `page=0,pagesize=20`
- `page=0,pagesize=0`

当前不能直接假设：

- `pagesize=0` 一定表示全量
- `page=0` 在所有接口里都表示“第一页”

库存域后续必须优先验证分页终止条件。

### 3.2 视图枚举风险

库存域是当前枚举风险最高的域。

已知枚举字段包括：

- `rtype`
  - 当前样本已知 `1/2/3`
  - 极可能代表不同统计视图
- `stockflag`
  - 当前样本已见 `0`
  - 尚未确认其他值
- `datetype`
  - 当前样本已见 `1`
- `type`
  - 当前样本是 `"已出库,已入库,在途"` 这样的组合字符串
- `doctype`
  - 当前样本是 `"1,2,3,4,5,6,7"`

这些参数里至少一部分不是“筛子”，而是“切视图”。

未探明前，不能把不同枚举值对应的数据直接拼在一起。

---

## 4. 维度重叠与失真风险

库存域当前至少有三层接口：

- 准明细候选：
  - `库存明细统计`
  - `出入库单据`
- 宽表分析候选：
  - `库存多维分析`
  - `进销存统计`
  - `日进销存`
- 结果视图候选：
  - `库存总和分析`
  - `库存零售统计`

当前规则：

- `库存明细统计` 优先视为库存事实源候选
- `出入库单据` 优先视为库存单据源候选
- `库存多维分析` 和 `进销存统计` 先当对账或分析宽表
- `库存总和分析` 只当视图快照，不直接进入事实链

---

## 5. 零售价、金额与成本字段现状

### 5.1 `库存明细统计`

当前真实样本已确认：

- 存在 `RetailPrice`
- 未确认存在 `CostPrice`

当前结论：

- 该接口可以提供库存维度的零售价观察
- 但不能据此推断已经拿到成本价

### 5.2 `库存多维分析`

当前样本里已能对上：

- `AStock`
- `AMoney`

但当前不能直接把 `AMoney` 解释成“成本金额”。

更保守的结论是：

- 这是某种金额聚合字段
- 在未核实列头、页面含义和角色差异前，不把它直接映射成成本

---

## 6. 当前建议

- 主源候选：
  - `库存明细统计`
  - `出入库单据`
- 分析/对账候选：
  - `库存多维分析`
  - `进销存统计`
  - `日进销存`
- 快照候选：
  - `库存总和分析-*`
  - `库存零售统计`

---

## 7. 当前探索策略

当前自动探索只先覆盖：

### 7.1 `库存明细统计`

- 先探测 `page/pagesize`
- 再探测 `stockflag`
- 当前实现会把 `stockflag` 和分页探测组合起来看

当前目标：

- 判断是否真的存在额外页
- 判断 `stockflag` 是切视图还是切范围
- 判断 `RetailPrice`、其他金额字段是否随 `stockflag` 变化

### 7.2 `出入库单据`

- 先探测 `page/pagesize`
- 先探测 `datetype`
- `type` 和 `doctype` 当前只保留样本里的组合值，不第一轮拆全组合

当前目标：

- 判断 `datetype` 是否显著改变数据集
- 判断该接口是否值得进入库存单据主链
- 在不放大组合爆炸的前提下先确认分页语义

### 7.3 第一轮真实探索结论

- `库存明细统计`
  - `stockflag=0/1/2` 已出现真实返回签名差异，说明不能把它当成纯展示参数
  - `page=1` 在部分 `stockflag` 组合下也出现了不同返回签名，分页语义需要继续确认
  - 当前更适合先按“枚举 sweep + 分页验证”继续推进，而不是直接认定为单请求全量源
- `出入库单据`
  - `datetype=1/2` 已出现真实返回签名差异，说明它大概率会切数据集
  - `page=1` 也出现了不同返回签名，后续需要继续确认是否是真实翻页还是服务端的特殊行为
  - `type`、`doctype` 仍先保留当前样本组合值，不在第一轮做全组合展开

---

## 8. 后续待验证事项

1. `库存明细统计.page=0/pagesize=20` 是否需要持续翻页
2. `stockflag` 是否影响数据范围还是只影响展示视图
3. `rtype=1/2/3` 是否是互斥视图，还是同一数据源不同切片
4. `出入库单据.datetype/type/doctype` 的可选值全集是什么
5. `库存多维分析.AMoney` 对应页面上的真实列头到底是什么
6. 不同角色账号下库存接口是否会显式返回成本字段
