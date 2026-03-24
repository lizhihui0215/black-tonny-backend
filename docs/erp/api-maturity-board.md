# ERP API 成熟度总览

> 本文件由 `scripts/build_erp_api_maturity_board.py` 生成，作为后续推进的唯一状态面板。执行路线图见 [ERP Capture 全量导入路线图](./capture-ingestion-roadmap.md)。

## 1. 当前目标

- 在当前合法账号/角色可见范围内，先把所有可读报表与查询数据做成完整风险地图，再按可信度分层纳入主链。
- `capture` 负责原始留痕，`serving` 继续只做可演进投影；在全域风险地图完成前，不新增正式 capture 主链路线。
- 后续推进一律以本总览为入口：先看总览，再看路线图，再看对应 ledger 与 analysis 证据文件。

## 2. 全域门槛与主链准入标准

- 当前账号可见全域已经完成菜单覆盖审计；所有可见页面都已分类到 covered / visible_but_untracked / visible_but_failed / container_only
- 已知读接口路线都至少完成风险地图（基线 + 分页/枚举/范围风险 + 主源/快照分类）
- 页面研究已确认接口语义
- 纯 HTTP 可稳定重放
- 关键参数已分清视图切换或数据范围切换
- 分页语义已确认
- 至少有一条对账或证据闭环可解释主要指标
- 当前没有高优先级 issue_flags

## 3. 当前总体状态

- 路线总数：`35`
- 路线级风险地图已完成：`35 / 35`
- 当前账号可见菜单覆盖审计完成：`是`
- 当前账号可点击页面：`32`
- 已覆盖页面：`32`
- visible_but_untracked：`0`
- visible_but_failed：`0`
- container_only：`8`
- 全域门槛已达成：`是`
- 已准入主链：`11`
- 已真实写入 capture：`20`
- 已 HTTP 回证：`20`
- 已单变量：`4`
- 仅基线：`11`
- 仅发现：`0`
- 能跑但不能信：`12`
- 中等可信：`23`
- 高可信：`0`

当前高优先级 blocker：
- `5` 次：尚未完成分页/枚举确认
- `4` 次：配置/设置类页面，默认不进入事实主链
- `3` 次：尚未确认是否只保留结果快照定位
- `2` 次：尚未完成单变量探测
- `2` 次：尚未完成 HTTP 回证
- `1` 次：当前 seed type 值全部触发服务端错误
- `1` 次：服务端 SQL 截断错误仍未解除
- `1` 次：尚未确认可稳定返回数据的 type 取值

## 4. 分域状态

| 域 | 路线数 | 风险地图完成 | 已HTTP回证 | 已单变量 | 仅基线 | 仅发现 | 中高可信 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 销售 | 13 | 13 | 7 | 0 | 6 | 0 | 7 |
| 库存 | 9 | 9 | 2 | 3 | 4 | 0 | 5 |
| 会员 | 5 | 5 | 4 | 0 | 1 | 0 | 4 |
| 储值 | 3 | 3 | 3 | 0 | 0 | 0 | 3 |
| 流水单据 | 5 | 5 | 4 | 1 | 0 | 0 | 4 |

## 5. 路线状态板

### 销售

| 路线 | 来源分类 | 阶段 | 风险地图完成 | 覆盖状态 | 可信度 | 全域门槛阻塞 | 主链就绪 | 已写capture | 最新batch | 菜单路径 | 剩余问题 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GetDIYReportData(E004001008_2) | 主源候选 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 是 | 是 | `7d361ed0079f4584871996db0cf721e5` | 报表管理 / 零售报表 / 销售清单 | - | 已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。 |
| SelSaleReport | 主源候选 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 是 | 是 | `7d361ed0079f4584871996db0cf721e5` | 报表管理 / 零售报表 / 销售清单 | - | 已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。 |
| 商品资料 / SelWareList | 主源候选 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 是 | 是 | `453246095da848939df0c7f2768f9b0c` | 基础资料 / 商品资料 | - | 已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。 |
| 客户资料 / SelDeptList | 主源候选 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 是 | 是 | `65eb6cbf325d4cccb610c91b3fd0ef5b` | 基础资料 / 客户资料 | - | 已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。 |
| SelDeptSaleList | 对账源 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 否 | 否 | `-` | 报表管理 / 零售报表 / 零售明细统计 | - | 保持研究/对账源定位，补充极端单日窗口的 edge case 说明即可 |
| sales_reverse_document_lines | 研究留痕 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 否 | 是 | `7d361ed0079f4584871996db0cf721e5` | 报表管理 / 零售报表 / 销售清单 | - | 继续保持 capture 研究留痕，不进入 serving 或 dashboard 主链 |
| 商品销售情况 / SelSaleReportData | 结果快照 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 否 | 是 | `6dc6fa6f416345639f9b41a41fceeb42` | 报表管理 / 综合分析 / 商品销售情况 | - | 商品销售情况已满足 snapshot capture 条件；按默认时间窗单请求写入 capture，并继续保持结果快照定位。 |
| 门店销售月报 / DeptMonthSalesReport | 结果快照 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 报表管理 / 综合分析 / 门店销售月报 | 尚未完成分页/枚举确认 | 补 门店销售月报 的分页/枚举确认，保持结果快照定位 |
| 参数设置 / page_baseline | 未采纳 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 其他 / 参数设置 | 配置/设置类页面，默认不进入事实主链 | 保持 参数设置 为未采纳；若后续确认有长期分析价值，再单独评估 snapshot 路线 |
| 导购员设置 / page_baseline | 未采纳 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 其他 / 导购员设置 | 配置/设置类页面，默认不进入事实主链 | 保持 导购员设置 为未采纳；若后续确认有长期分析价值，再单独评估 snapshot 路线 |
| 小票设置 / page_baseline | 未采纳 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 其他 / 小票设置 | 配置/设置类页面，默认不进入事实主链 | 保持 小票设置 为未采纳；若后续确认有长期分析价值，再单独评估 snapshot 路线 |
| 店铺定位 / GetControlData | 未采纳 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 其他 / 店铺定位 | 配置/设置类页面，默认不进入事实主链 | 保持 店铺定位 为未采纳；若后续确认有长期分析价值，再单独评估 snapshot 路线 |
| 店铺零售清单 / GetDIYReportData | 未采纳 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 报表管理 / 零售报表 / 店铺零售清单 | 尚未完成单变量探测；尚未完成 HTTP 回证 | 补 店铺零售清单 的单变量探测与 HTTP 回证 |

### 库存

| 路线 | 来源分类 | 阶段 | 风险地图完成 | 覆盖状态 | 可信度 | 全域门槛阻塞 | 主链就绪 | 已写capture | 最新batch | 菜单路径 | 剩余问题 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 出入库单据 / SelOutInStockReport | 主源候选 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 是 | 是 | `d5e1b38acc814a68b17c64652eba405f` | 报表管理 / 进出报表 / 出入库单据 | - | 已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。 |
| 库存明细统计 / SelDeptStockWaitList | 主源候选 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 是 | 是 | `93b8fa4252c345b190de5b2b2751c391` | 报表管理 / 库存报表 / 库存明细统计 | - | 已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。 |
| 库存总和分析-按中分类 / SelStockAnalysisList | 结果快照 | 已单变量 | 是 | covered | 中等可信 | 否 | 否 | 否 | `-` | 报表管理 / 库存报表 / 库存综合分析 | 尚未确认是否只保留结果快照定位 | 确认 库存总和分析-按中分类 是否继续只做结果快照 |
| 库存总和分析-按年份季节 / SelStockAnalysisList | 结果快照 | 已单变量 | 是 | covered | 中等可信 | 否 | 否 | 否 | `-` | 报表管理 / 库存报表 / 库存综合分析 | 尚未确认是否只保留结果快照定位 | 确认 库存总和分析-按年份季节 是否继续只做结果快照 |
| 库存总和分析-按波段 / SelStockAnalysisList | 结果快照 | 已单变量 | 是 | covered | 中等可信 | 否 | 否 | 否 | `-` | 报表管理 / 库存报表 / 库存综合分析 | 尚未确认是否只保留结果快照定位 | 确认 库存总和分析-按波段 是否继续只做结果快照 |
| 库存多维分析 / SelDeptStockAnalysis | 结果快照 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 报表管理 / 库存报表 / 库存多维分析 | 尚未完成分页/枚举确认 | 补 库存多维分析 的分页/枚举确认，保持结果快照定位 |
| 库存零售统计 / SelDeptStockSaleList | 结果快照 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 报表管理 / 库存报表 / 库存零售统计 | 尚未完成分页/枚举确认 | 补 库存零售统计 的分页/枚举确认，保持结果快照定位 |
| 日进销存 / SelInSalesReportByDay | 结果快照 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 报表管理 / 进出报表 / 日进销存 | 尚未完成分页/枚举确认 | 补 日进销存 的分页/枚举确认，保持结果快照定位 |
| 进销存统计 / SelInSalesReport | 结果快照 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 报表管理 / 进出报表 / 进销存统计 | 尚未完成分页/枚举确认 | 补 进销存统计 的分页/枚举确认，保持结果快照定位 |

### 会员

| 路线 | 来源分类 | 阶段 | 风险地图完成 | 覆盖状态 | 可信度 | 全域门槛阻塞 | 主链就绪 | 已写capture | 最新batch | 菜单路径 | 剩余问题 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 会员中心 / SelVipInfoList | 主源候选 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 是 | 是 | `38ae72ea2f5344c399c59409d51517b8` | 会员资料 / 会员中心 | - | 已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。 |
| 会员维护 / SelVipReturnVisitList | 主源候选 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 是 | 是 | `c26d550fa8ea49aa8c40b34fb3e95073` | 会员资料 / 会员维护 | - | 已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。 |
| 会员总和分析 / SelVipAnalysisReport | 结果快照 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 否 | 是 | `4690b28a62fb404881624040b8c75f93` | 报表管理 / 会员报表 / 会员综合分析 | - | 会员总和分析已满足 snapshot capture 条件；按 page=0 单请求写入 capture，并继续保持结果快照定位。 |
| 会员消费排行 / SelVipSaleRank | 结果快照 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 否 | 是 | `9c9f0548cb724672a218cbbe7af8acc9` | 报表管理 / 会员报表 / 会员消费排行 | - | 会员消费排行已满足 snapshot capture 条件；按 page=0 单请求写入 capture，并继续保持排行快照定位。 |
| VIP卡折扣管理 / 待识别 | 未采纳 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 其他 / VIP卡折扣管理 | 尚未完成单变量探测；尚未完成 HTTP 回证 | 补 VIP卡折扣管理 的单变量探测与 HTTP 回证 |

### 储值

| 路线 | 来源分类 | 阶段 | 风险地图完成 | 覆盖状态 | 可信度 | 全域门槛阻塞 | 主链就绪 | 已写capture | 最新batch | 菜单路径 | 剩余问题 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 储值卡明细 / GetDIYReportData | 主源候选 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 是 | 是 | `fa278535105e40529fa9c0020966b70a` | 报表管理 / 会员报表 / 储值卡明细 | - | 已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。 |
| 储值卡汇总 / GetDIYReportData | 结果快照 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 否 | 是 | `ef07a37eec634b239efbe43987949670` | 报表管理 / 会员报表 / 储值卡汇总 | - | 储值卡汇总已满足 snapshot capture 条件；按默认 Search 空值单请求写入 capture，并继续保持卡级汇总快照定位。 |
| 储值按店汇总 / GetDIYReportData | 结果快照 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 否 | 是 | `97a609b7e3a04043be42095ccf114157` | 报表管理 / 会员报表 / 储值按店汇总 | - | 储值按店汇总已满足 snapshot capture 条件；按默认时间窗单请求写入 capture，并继续保持门店级汇总快照定位。 |

### 流水单据

| 路线 | 来源分类 | 阶段 | 风险地图完成 | 覆盖状态 | 可信度 | 全域门槛阻塞 | 主链就绪 | 已写capture | 最新batch | 菜单路径 | 剩余问题 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 收货确认 / SelDocConfirmList | 主源候选 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 是 | 是 | `4f61becdb09342cda68916c5b39f38b8` | 单据管理 / 上级往来 / 收货确认 | - | 收货确认主列表已 admit；下一步应沿 receiveConfirm.menuId、父链 menuItemId.CheckDoc 与 detailData.currentItem 的断点继续回溯更早的上游数据注入点，并追 RTM_reportTable.props.tableData、allTableData/vxeTable.tableData、vxeTable.database 与 FXDATABASE/receiveConfirm_E003001001_1 本地表初始化的来源，确认为何 receiveConfirm / reportTableItem_mainRef / RTM_reportTable 三层都有分页状态却始终没有行数据。 |
| 退货明细 / SelReturnStockList | 主源候选 | 已HTTP回证 | 是 | covered | 能跑但不能信 | 否 | 否 | 是 | `1eb5e37d3f5643e08eaacdfc3b504dfa` | 报表管理 / 进出报表 / 退货明细 | 当前 seed type 值全部触发服务端错误；服务端 SQL 截断错误仍未解除；尚未确认可稳定返回数据的 type 取值；已验证的窄过滤 seed 仍全部触发服务端错误；已补测祖先状态暴露的 type=4/5 候选值，仍全部触发服务端错误；ReturnStockBaseInfo 当前 11 个可见筛选维度都已纳入 probe，问题已不在可见筛选遗漏；页面真实点击后的查询请求仍未改变 post body；组件诊断仍未暴露 route-level 过滤模型；已定位 RTM_searchConditions/RTM_getReportInfo，但调用后仍未触发新请求；RTM_reportTable 目前只暴露方法与 vxeTable 空条件状态，仍未看到可写筛选模型；RTM_searchConditions/RTM_getReportInfo 当前只暴露 native code 包装，仍无法从函数体反推出隐藏上下文；RTM_reportTable.vxeTable.database 已指向 FXDATABASE，但浏览器实际打开后 object_store_names 为空，salesReturnDetailReport 并未落成本地表；RTM_reportTable.searchConditions/searchDataInfo/pageCondition/getReportInfo/conditionStr 当前都只暴露 native code 包装；salesReturnDetailReport 根组件的查询/加载方法当前也只暴露 native code 包装，无法继续从根组件函数体反推上下文注入链；salesReturnDetailReport 父链壳层方法当前也只暴露 native code 包装，说明更早的菜单/页面注入链同样不可从函数体继续回溯；salesReturnDetail 自身 ref 当前只拿到 showLoading 回调，父链 navmenu 也未见任何附加数据载荷，说明壳层 ref 仍不是缺失退货数据的来源；store/root 当前只见 cleardata=false 与空 root_data_snapshot，仍未见任何退货数据缓存；localStorage/sessionStorage/window 当前只见登录态与通用字段，salesReturnDetailReport.vm 的 databaseTableName 仍为空；route/parent 注入上下文当前只有 menuItemId/reportLists 等壳层信息，未见额外退货查询参数 | 页面默认 payload、type seed 和已验证窄过滤仍全部报错；下一步应优先定位页面动作链或服务端字段边界，而不是继续盲加基础过滤 |
| 门店盘点单 / SelDocManageList | 主源候选 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 是 | 是 | `2f31764d5f414aba9af48fb7577faddf` | 单据管理 / 盘点业务 / 门店盘点单 | - | 门店盘点单主列表已可准入 capture；下一步应优先确认 getDiffData(row) 产出的本地损溢数据是否可作为二级 raw route，再决定是否继续追独立 HTTP 接口。 |
| 门店盘点单 / store_stocktaking_diff_records | 研究留痕 | 已单变量 | 是 | covered | 中等可信 | 否 | 否 | 是 | `5a1206e4be9340359e9a8b0ed14433e0` | 单据管理 / 盘点业务 / 门店盘点单 | 统计损溢当前更像本地派生数据，尚未确认独立 HTTP route；尚未确认多单据场景下 orderDiffData 是否稳定；按行调用 getDiffData(row_1) 当前会把 diff 状态清空，尚未证明多行稳定；按行调用 getDiffData(row_2) 当前仍未拿到稳定选中行 | 继续区分默认 getDiffData() 产出的损溢总表与按行 getDiffData(row) 的稳定性，再决定是否把本地损溢数据固定为长期二级 raw route。 |
| 每日流水单 / SelectRetailDocPaymentSlip | 结果快照 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 否 | 是 | `ff538d7129f74e8288023fc991618aab` | 报表管理 / 对账报表 / 每日流水单 | - | 每日流水单已满足 snapshot capture 条件；按默认窗口单请求写入 capture，并继续保持结果快照定位。 |

## 6. 当前推进顺序

1. 当前账号可见全域风险地图已经完成，下一步先执行销售首批 capture 准入。
2. 销售域正常路线按 `sales_documents_head` / `sales_document_lines` 进入 capture，`sales_reverse_document_lines` 只保留研究留痕。
3. 在 serving 继续冻结的前提下，先观测销售批次回归指标与异常阈值表现。
4. 再收口库存域的 `type`、`doctype` 与 `stockflag=1/2`。
5. 最后才轮到会员 / 储值 / 流水单据的 HTTP 回证与主链准入评估。

## 7. 证据来源

- `report_matrix`: `tmp/capture-samples/analysis/report-matrix-20260321-213132.json`
- `page_research_files`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260322-014358.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260322-014422.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260322-014739.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260322-015056.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260322-015133.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260322-021030.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260322-023512.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260322-024014.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260322-154152.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260322-223819.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260322-224740.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260322-225529.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260322-230604.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260322-232400.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260322-232647.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260322-232821.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260323-001449.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260323-012826.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260323-032304.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260323-034403.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260323-034504.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260323-040838.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260323-041053.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260323-041242.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260323-193745.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260323-194142.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260323-203047.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260323-203212.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260323-203853.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260323-204057.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260323-213114.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-20260323-214834.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-adhoc-no-date-20260323-192448.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-adhoc-no-date-20260323-192526.json`
  - `tmp/capture-samples/analysis/yeusoft-page-research-adhoc-no-date-20260323-192728.json`
- `sales_evidence`: `tmp/capture-samples/analysis/sales-evidence-chain-20260322-171553.json`
- `inventory_evidence`: `tmp/capture-samples/analysis/inventory-evidence-chain-20260322-184350.json`
- `store_stocktaking_evidence`: `tmp/capture-samples/analysis/store-stocktaking-evidence-chain-20260323-212759.json`
- `return_detail_evidence`: `tmp/capture-samples/analysis/return-detail-evidence-chain-20260325-001804.json`
- `return_detail_ui_probe`: `tmp/capture-samples/analysis/return-detail-ui-probe-20260325-004232.json`
- `receipt_confirmation_evidence`: `tmp/capture-samples/analysis/receipt-confirmation-evidence-chain-20260323-213708.json`
- `receipt_confirmation_ui_probe`: `tmp/capture-samples/analysis/receipt-confirmation-ui-probe-20260324-234341.json`
- `member_evidence`: `tmp/capture-samples/analysis/member-evidence-chain-20260323-041959.json`
- `member_maintenance_evidence`: `tmp/capture-samples/analysis/member-maintenance-evidence-chain-20260323-215559.json`
- `member_analysis_snapshot_evidence`: `tmp/capture-samples/analysis/member-analysis-snapshot-evidence-chain-20260325-013702.json`
- `member_sales_rank_snapshot_evidence`: `tmp/capture-samples/analysis/member-sales-rank-snapshot-evidence-chain-20260325-012148.json`
- `product_evidence`: `tmp/capture-samples/analysis/product-evidence-chain-20260323-005323.json`
- `product_sales_snapshot_evidence`: `tmp/capture-samples/analysis/product-sales-snapshot-evidence-chain-20260325-003705.json`
- `daily_payment_snapshot_evidence`: `tmp/capture-samples/analysis/daily-payment-snapshot-evidence-chain-20260325-005717.json`
- `stored_value_card_summary_snapshot_evidence`: `tmp/capture-samples/analysis/stored-value-card-summary-snapshot-evidence-chain-20260325-015258.json`
- `stored_value_by_store_snapshot_evidence`: `tmp/capture-samples/analysis/stored-value-by-store-snapshot-evidence-chain-20260325-015258.json`
- `customer_evidence`: `tmp/capture-samples/analysis/customer-evidence-chain-20260323-214755.json`
- `stored_value_evidence`: `tmp/capture-samples/analysis/stored-value-evidence-chain-20260323-211309.json`
- `inventory_outin_research`: `tmp/capture-samples/analysis/inventory-outin-capture-research-20260322-200314.json`
- `menu_coverage_audit`: `tmp/capture-samples/analysis/menu-coverage-audit-20260322-154931.json`
- `capture_runtime_files`
  - `tmp/capture-samples/analysis/customer-capture-admission-20260323-214755.json`
  - `tmp/capture-samples/analysis/customer-capture-research-20260322-230649.json`
  - `tmp/capture-samples/analysis/daily-payment-snapshot-capture-admission-20260325-005723.json`
  - `tmp/capture-samples/analysis/inventory-outin-capture-admission-20260322-191557.json`
  - `tmp/capture-samples/analysis/inventory-outin-capture-admission-20260322-192223.json`
  - `tmp/capture-samples/analysis/inventory-outin-capture-admission-20260322-200625.json`
  - `tmp/capture-samples/analysis/inventory-outin-capture-research-20260322-190149.json`
  - `tmp/capture-samples/analysis/inventory-outin-capture-research-20260322-191002.json`
  - `tmp/capture-samples/analysis/inventory-outin-capture-research-20260322-191017.json`
  - `tmp/capture-samples/analysis/inventory-outin-capture-research-20260322-191052.json`
  - `tmp/capture-samples/analysis/inventory-outin-capture-research-20260322-191238.json`
  - `tmp/capture-samples/analysis/inventory-outin-capture-research-20260322-192049.json`
  - `tmp/capture-samples/analysis/inventory-outin-capture-research-20260322-200314.json`
  - `tmp/capture-samples/analysis/inventory-stock-capture-admission-20260322-190149.json`
  - `tmp/capture-samples/analysis/inventory-stock-capture-admission-20260322-190925.json`
  - `tmp/capture-samples/analysis/inventory-stock-capture-admission-20260322-200250.json`
  - `tmp/capture-samples/analysis/member-analysis-snapshot-capture-admission-20260325-013718.json`
  - `tmp/capture-samples/analysis/member-capture-admission-20260323-042004.json`
  - `tmp/capture-samples/analysis/member-capture-research-20260322-202444.json`
  - `tmp/capture-samples/analysis/member-maintenance-capture-admission-20260323-215559.json`
  - `tmp/capture-samples/analysis/member-maintenance-capture-research-20260323-204524.json`
  - `tmp/capture-samples/analysis/member-sales-rank-snapshot-capture-admission-20260325-012205.json`
  - `tmp/capture-samples/analysis/product-capture-admission-20260323-005308.json`
  - `tmp/capture-samples/analysis/product-capture-admission-20260323-005413.json`
  - `tmp/capture-samples/analysis/product-capture-research-20260322-225304.json`
  - `tmp/capture-samples/analysis/product-sales-snapshot-capture-admission-20260325-003720.json`
  - `tmp/capture-samples/analysis/receipt-confirmation-capture-admission-20260323-213708.json`
  - `tmp/capture-samples/analysis/receipt-confirmation-capture-admission-20260323-224355.json`
  - `tmp/capture-samples/analysis/receipt-confirmation-capture-research-20260323-034146.json`
  - `tmp/capture-samples/analysis/return-detail-capture-research-20260324-230648.json`
  - `tmp/capture-samples/analysis/sales-capture-admission-20260322-200741.json`
  - `tmp/capture-samples/analysis/store-stocktaking-capture-admission-20260323-212815.json`
  - `tmp/capture-samples/analysis/store-stocktaking-capture-admission-20260323-224356.json`
  - `tmp/capture-samples/analysis/store-stocktaking-capture-research-20260323-033511.json`
  - `tmp/capture-samples/analysis/store-stocktaking-diff-capture-research-20260324-002315.json`
  - `tmp/capture-samples/analysis/stored-value-by-store-snapshot-capture-admission-20260325-015321.json`
  - `tmp/capture-samples/analysis/stored-value-capture-admission-20260323-211337.json`
  - `tmp/capture-samples/analysis/stored-value-capture-admission-20260323-224354.json`
  - `tmp/capture-samples/analysis/stored-value-capture-research-20260323-200113.json`
  - `tmp/capture-samples/analysis/stored-value-card-summary-snapshot-capture-admission-20260325-015321.json`
- `ledger_files`
  - `docs/erp/sales-ledger.md`
  - `docs/erp/inventory-ledger.md`
  - `docs/erp/member-ledger.md`
  - `docs/erp/stored-value-ledger.md`
  - `docs/erp/payment-and-doc-ledger.md`
