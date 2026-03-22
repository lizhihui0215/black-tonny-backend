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

### 7.3 第二轮单变量深挖结论

当前还新增了一条库存主线 HTTP 证据闭环脚本：

- 脚本：`scripts/analyze_yeusoft_inventory_evidence_chain.py`
- 最新输出：`tmp/capture-samples/analysis/inventory-evidence-chain-20260322-174203.json`

- `库存明细统计`
  - 第二轮页面研究确认它的主数据接口仍然是 `SelDeptStockWaitList`
  - 最新 HTTP 证据输出：
    - `tmp/capture-samples/analysis/inventory-evidence-chain-20260322-184350.json`
    - `tmp/capture-samples/analysis/inventory-capture-admission-20260322-184314.json`
  - `stockflag=0/1/2` 的 HTTP probe 已经形成稳定结论：
    - `stockflag=0`：`974` 行
    - `stockflag=1`：`1548` 行
    - `stockflag=2`：`1548` 行
  - 三个值的列结构保持一致，但 `row_set_signature` 在 `0` 与 `1/2` 间明显不同
  - 当前可以明确把 `stockflag` 判成 `data_subset_or_scope_switch`
  - 在当前账号样本下，`stockflag=1` 与 `stockflag=2` 数据集一致，因此当前 capture 候选参数计划已经收成：
    - `stockflag_values = [0, 1]`
    - `stockflag=2` 视为与 `1` 等价的重复范围值
  - `page=0/1` 在纯 HTTP 下当前返回同一数据集
  - 当前对分页的正式判断已经从“待解释 blocker”收成：
    - capture 正式抓取固定 `page=0`
    - `page` 当前不作为库存明细统计主链的正式分页参数
  - 这条路线现在已经可以进入 `capture candidate`，route 名固定为 `inventory_stock_wait_lines`
- `出入库单据`
  - 第二轮页面研究确认它的主数据接口仍然是 `SelOutInStockReport`
  - `datetype=1/2` 的单变量 probe 已形成稳定结论：
    - `datetype=1`：`311` 行
    - `datetype=2`：`312` 行
  - 两者列结构一致，但数据集不同，当前可明确判成 `data_subset_or_scope_switch`
  - `type=已出库` 单独探测时返回 `158` 行
  - `doctype=1` 单独探测时返回 `74` 行
  - 最新 HTTP 证据链进一步确认：
    - `datetype`
    - `type`
    - `doctype`
    都会切换数据范围
  - 当前正式候选 sweep 集已经收成：
    - `datetype = [1, 2]`
    - `type = [已出库, 已入库, 在途]`
    - `doctype = [1, 2, 3, 7]`
  - 其中 `doctype=3/4/5/6` 当前在样本中属于等价组，最小 sweep 集先保留 `3`
  - 这条路线当前仍然不能直接进入 capture 主链，剩余 blocker 只剩：
    - `doctype` 的分组语义还要再做一次受控确认
    - 还需要验证 `datetype × type × doctype` 的最小组合 sweep 是否稳定覆盖单据集合
- `库存综合分析`
  - 第二轮页面研究对 `rtype=1/2/3` 做了直接单变量 probe
  - 当前结果是：
    - `rtype=1`：`14` 行
    - `rtype=2`：`13` 行
    - `rtype=3`：`1` 行
  - 不同 `rtype` 的列结构和数据集都发生变化
  - 当前更适合把它判成 `mixed`
  - 这说明它更像“同一父页面下的分析变体集合”，不应直接当成统一事实接口接入主链

### 7.4 第一轮真实探索结论

- `库存明细统计`
  - `stockflag=0/1/2` 已确认不是纯展示参数
  - 当前 `stockflag` 的枚举语义更接近“切数据子集/范围”：
    - `stockflag=0` 返回 `975` 行
    - `stockflag=1` 返回 `1548` 行
    - `stockflag=2` 返回 `1548` 行，且当前样本下与 `stockflag=1` 的数据集一致
  - 列结构在 `0/1/2` 间保持一致，差异主要在数据集合本身，不像单纯切视图
  - `page=1` 在部分 `stockflag` 组合下也出现了不同数据集，分页语义需要继续确认
  - 当前更适合先按“枚举 sweep + 分页验证”继续推进，而不是直接认定为单请求全量源
- `出入库单据`
  - 当前解析已下钻到 `retdata[0].Data`，不再只看外层 `Count/HJ/Data`
  - `datetype=1/2` 已确认更接近“切数据子集/时间口径”，不是单纯切视图：
    - `datetype=1` 返回 `311` 行
    - `datetype=2` 返回 `312` 行
    - 两者列结构一致，但数据集不同
  - `page=1` 也返回了新的 20 行数据，当前更像真实翻页而不是单纯重复首屏
  - `type`、`doctype` 仍先保留当前样本组合值，不在第一轮做全组合展开

### 7.5 首屏 page-size 研究结论

- `库存明细统计`
  - 当前会固定比较 `20 / 100 / 1000 / 10000 / 0` 的首屏行为
  - 当前真实探测里，`20 / 100 / 1000 / 10000 / 0` 都返回 `975` 行
  - 顺序敏感签名会变化，但顺序无关的 `row_set_signature` 已确认一致
  - 这说明它更像“同一批数据只是返回顺序不同”，而不是“大页参数拿到了更多数据”
  - 当前推荐第一页大小仍保持 `20`
  - 当前可标记为 `large_page_ignored`，不需要为了首屏多拿数据而放大默认 `pagesize`
  - 如果 `10000` 或 `0` 已经触发 `10000` 行阈值，才会追加更大的 edge size 做边缘试探
- `出入库单据`
  - 同样先做首屏 page-size 对比，再决定是否值得往正式抓取器回写
  - 当前真实探测里，`20 / 100 / 1000 / 10000 / 0` 的首屏返回完全一致，当前推荐第一页大小保持 `20`
  - 在分页语义没完全坐实前，大页探测只作为研究结论，不自动切主链参数

### 7.6 页面研究链如何服务库存域

库存域后续会结合浏览器页面研究链，重点解决两类问题：

- 页面控件到底如何驱动 `stockflag / datetype / type / doctype`
- 哪些页面动作是在切视图，哪些页面动作是在切数据范围

页面研究链只负责产出证据链：

- 动作
- 请求
- 参数差分
- 响应签名摘要

真正的正式抓取仍然回落到纯 HTTP。

对应运行说明见：

- `docs/erp/page-research-runbook.md`

---

## 8. 后续待验证事项

1. `库存明细统计.page=0/pagesize=20` 是否需要持续翻页
2. `stockflag` 是否影响数据范围还是只影响展示视图
3. `rtype=1/2/3` 是否是互斥视图，还是同一数据源不同切片
4. `出入库单据.datetype/type/doctype` 的可选值全集是什么
5. `库存多维分析.AMoney` 对应页面上的真实列头到底是什么
6. 不同角色账号下库存接口是否会显式返回成本字段
