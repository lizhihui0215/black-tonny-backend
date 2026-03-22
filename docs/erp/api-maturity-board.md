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

- 路线总数：`34`
- 路线级风险地图已完成：`34 / 34`
- 当前账号可见菜单覆盖审计完成：`是`
- 当前账号可点击页面：`32`
- 已覆盖页面：`32`
- visible_but_untracked：`0`
- visible_but_failed：`0`
- container_only：`8`
- 全域门槛已达成：`是`
- 已准入主链：`0`
- 已真实写入 capture：`8`
- 已 HTTP 回证：`9`
- 已单变量：`3`
- 仅基线：`22`
- 仅发现：`0`
- 能跑但不能信：`23`
- 中等可信：`11`
- 高可信：`0`

当前高优先级 blocker：
- `10` 次：尚未完成分页/枚举确认
- `6` 次：尚未完成单变量探测
- `6` 次：尚未完成 HTTP 回证
- `4` 次：配置/设置类页面，默认不进入事实主链
- `3` 次：尚未确认是否只保留结果快照定位
- `1` 次：warecause 语义仍待确认
- `1` 次：condition 语义仍待确认
- `1` 次：是否存在服务端上限仍待确认

## 4. 分域状态

| 域 | 路线数 | 风险地图完成 | 已HTTP回证 | 已单变量 | 仅基线 | 仅发现 | 中高可信 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 销售 | 13 | 13 | 5 | 0 | 8 | 0 | 5 |
| 库存 | 9 | 9 | 2 | 3 | 4 | 0 | 5 |
| 会员 | 5 | 5 | 1 | 0 | 4 | 0 | 1 |
| 储值 | 3 | 3 | 0 | 0 | 3 | 0 | 0 |
| 流水单据 | 4 | 4 | 1 | 0 | 3 | 0 | 0 |

## 5. 路线状态板

### 销售

| 路线 | 来源分类 | 阶段 | 风险地图完成 | 覆盖状态 | 可信度 | 全域门槛阻塞 | 主链就绪 | 已写capture | 最新batch | 菜单路径 | 剩余问题 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GetDIYReportData(E004001008_2) | 主源候选 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 否 | 是 | `7d361ed0079f4584871996db0cf721e5` | 报表管理 / 零售报表 / 销售清单 | - | 已可按 sale_no 分流正常明细与逆向明细，准备首批 capture 准入 |
| SelSaleReport | 主源候选 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 否 | 是 | `7d361ed0079f4584871996db0cf721e5` | 报表管理 / 零售报表 / 销售清单 | - | 已具备首批 capture 准入条件，保持 serving 冻结并先观测批次回归指标 |
| 商品资料 / SelWareList | 主源候选 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 否 | 是 | `ac05374992f645acbefc2f9383dd480f` | 基础资料 / 商品资料 | warecause 语义仍待确认 | 继续确认 warecause 的业务范围；若无额外限制，可按大页尺寸顺序翻页进入首批 capture admit |
| 客户资料 / SelDeptList | 主源候选 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 是 | `7608a0670e1d44aea20fb886530da93f` | 基础资料 / 客户资料 | 尚未完成单变量探测；尚未完成 HTTP 回证 | 补 客户资料 的单变量探测与 HTTP 回证 |
| SelDeptSaleList | 对账源 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 否 | 否 | `-` | 报表管理 / 零售报表 / 零售明细统计 | - | 保持研究/对账源定位，补充极端单日窗口的 edge case 说明即可 |
| sales_reverse_document_lines | 研究留痕 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 否 | 是 | `7d361ed0079f4584871996db0cf721e5` | 报表管理 / 零售报表 / 销售清单 | - | 继续保持 capture 研究留痕，不进入 serving 或 dashboard 主链 |
| 商品销售情况 / SelSaleReportData | 结果快照 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 报表管理 / 综合分析 / 商品销售情况 | 尚未完成分页/枚举确认 | 补 商品销售情况 的分页/枚举确认，保持结果快照定位 |
| 门店销售月报 / DeptMonthSalesReport | 结果快照 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 报表管理 / 综合分析 / 门店销售月报 | 尚未完成分页/枚举确认 | 补 门店销售月报 的分页/枚举确认，保持结果快照定位 |
| 参数设置 / page_baseline | 未采纳 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 其他 / 参数设置 | 配置/设置类页面，默认不进入事实主链 | 保持 参数设置 为未采纳；若后续确认有长期分析价值，再单独评估 snapshot 路线 |
| 导购员设置 / page_baseline | 未采纳 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 其他 / 导购员设置 | 配置/设置类页面，默认不进入事实主链 | 保持 导购员设置 为未采纳；若后续确认有长期分析价值，再单独评估 snapshot 路线 |
| 小票设置 / page_baseline | 未采纳 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 其他 / 小票设置 | 配置/设置类页面，默认不进入事实主链 | 保持 小票设置 为未采纳；若后续确认有长期分析价值，再单独评估 snapshot 路线 |
| 店铺定位 / GetControlData | 未采纳 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 其他 / 店铺定位 | 配置/设置类页面，默认不进入事实主链 | 保持 店铺定位 为未采纳；若后续确认有长期分析价值，再单独评估 snapshot 路线 |
| 店铺零售清单 / GetDIYReportData | 未采纳 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 报表管理 / 零售报表 / 店铺零售清单 | 尚未完成单变量探测；尚未完成 HTTP 回证 | 补 店铺零售清单 的单变量探测与 HTTP 回证 |

### 库存

| 路线 | 来源分类 | 阶段 | 风险地图完成 | 覆盖状态 | 可信度 | 全域门槛阻塞 | 主链就绪 | 已写capture | 最新batch | 菜单路径 | 剩余问题 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 出入库单据 / SelOutInStockReport | 主源候选 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 否 | 是 | `d5e1b38acc814a68b17c64652eba405f` | 报表管理 / 进出报表 / 出入库单据 | - | 库存单据已具备 capture 候选准入条件，按最小组合 sweep 进入批次留痕 |
| 库存明细统计 / SelDeptStockWaitList | 主源候选 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 否 | 是 | `93b8fa4252c345b190de5b2b2751c391` | 报表管理 / 库存报表 / 库存明细统计 | - | 库存明细统计已具备 capture 候选准入条件，按 stockflag=0/1 双范围留痕并固定 page=0 |
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
| 会员中心 / SelVipInfoList | 主源候选 | 已HTTP回证 | 是 | covered | 中等可信 | 否 | 否 | 是 | `8cbfc3febcaf4427815c6e7af0439e92` | 会员资料 / 会员中心 | condition 语义仍待确认；是否存在服务端上限仍待确认 | 继续从页面控件或接口上下文反推 condition 合法值，并确认是否存在服务端上限，再评估 capture 准入 |
| 会员维护 / 待识别 | 主源候选 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 会员资料 / 会员维护 | 尚未完成单变量探测；尚未完成 HTTP 回证 | 补 会员维护 的单变量探测与 HTTP 回证 |
| 会员总和分析 / SelVipAnalysisReport | 结果快照 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 报表管理 / 会员报表 / 会员综合分析 | 尚未完成分页/枚举确认 | 补 会员总和分析 的分页/枚举确认，保持结果快照定位 |
| 会员消费排行 / SelVipSaleRank | 结果快照 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 报表管理 / 会员报表 / 会员消费排行 | 尚未完成分页/枚举确认 | 补 会员消费排行 的分页/枚举确认，保持结果快照定位 |
| VIP卡折扣管理 / 待识别 | 未采纳 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 其他 / VIP卡折扣管理 | 尚未完成单变量探测；尚未完成 HTTP 回证 | 补 VIP卡折扣管理 的单变量探测与 HTTP 回证 |

### 储值

| 路线 | 来源分类 | 阶段 | 风险地图完成 | 覆盖状态 | 可信度 | 全域门槛阻塞 | 主链就绪 | 已写capture | 最新batch | 菜单路径 | 剩余问题 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 储值卡明细 / GetDIYReportData | 主源候选 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 报表管理 / 会员报表 / 储值卡明细 | Search 语义仍待确认；尚未确认是否存在隐藏分页或服务端上限 | 先补 Search 语义与分页上限验证，再评估储值域主源准入 |
| 储值卡汇总 / GetDIYReportData | 结果快照 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 报表管理 / 会员报表 / 储值卡汇总 | 尚未完成分页/枚举确认 | 补 储值卡汇总 的分页/枚举确认，保持结果快照定位 |
| 储值按店汇总 / GetDIYReportData | 结果快照 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 报表管理 / 会员报表 / 储值按店汇总 | 尚未完成分页/枚举确认 | 补 储值按店汇总 的分页/枚举确认，保持结果快照定位 |

### 流水单据

| 路线 | 来源分类 | 阶段 | 风险地图完成 | 覆盖状态 | 可信度 | 全域门槛阻塞 | 主链就绪 | 已写capture | 最新batch | 菜单路径 | 剩余问题 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 退货明细 / SelReturnStockList | 主源候选 | 已HTTP回证 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 报表管理 / 进出报表 / 退货明细 | 当前 seed type 值全部触发服务端错误；服务端 SQL 截断错误仍未解除；尚未确认可稳定返回数据的 type 取值；已验证的窄过滤 seed 仍全部触发服务端错误 | 页面默认 payload、type seed 和已验证窄过滤仍全部报错；下一步应优先定位页面动作链或服务端字段边界，而不是继续盲加基础过滤 |
| 收货确认 / GetViewGridList | 主源候选 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 单据管理 / 上级往来 / 收货确认 | 尚未完成单变量探测；尚未完成 HTTP 回证 | 补 收货确认 的单变量探测与 HTTP 回证 |
| 门店盘点单 / GetViewGridList | 主源候选 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 单据管理 / 盘点业务 / 门店盘点单 | 尚未完成单变量探测；尚未完成 HTTP 回证 | 补 门店盘点单 的单变量探测与 HTTP 回证 |
| 每日流水单 / SelectRetailDocPaymentSlip | 结果快照 | 已基线 | 是 | covered | 能跑但不能信 | 否 | 否 | 否 | `-` | 报表管理 / 对账报表 / 每日流水单 | SearchType 的完整枚举未确认；尚未确认是否存在分页或数量限制 | 补 SearchType 枚举和分页限制研究，保持结果快照定位 |

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
- `sales_evidence`: `tmp/capture-samples/analysis/sales-evidence-chain-20260322-171553.json`
- `inventory_evidence`: `tmp/capture-samples/analysis/inventory-evidence-chain-20260322-184350.json`
- `return_detail_evidence`: `tmp/capture-samples/analysis/return-detail-evidence-chain-20260322-235002.json`
- `member_evidence`: `tmp/capture-samples/analysis/member-evidence-chain-20260322-200117.json`
- `product_evidence`: `tmp/capture-samples/analysis/product-evidence-chain-20260323-004130.json`
- `inventory_outin_research`: `tmp/capture-samples/analysis/inventory-outin-capture-research-20260322-200314.json`
- `menu_coverage_audit`: `tmp/capture-samples/analysis/menu-coverage-audit-20260322-154931.json`
- `capture_runtime_files`
  - `tmp/capture-samples/analysis/customer-capture-research-20260322-230649.json`
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
  - `tmp/capture-samples/analysis/member-capture-research-20260322-202444.json`
  - `tmp/capture-samples/analysis/product-capture-research-20260322-225304.json`
  - `tmp/capture-samples/analysis/sales-capture-admission-20260322-200741.json`
- `ledger_files`
  - `docs/erp/sales-ledger.md`
  - `docs/erp/inventory-ledger.md`
  - `docs/erp/member-ledger.md`
  - `docs/erp/stored-value-ledger.md`
  - `docs/erp/payment-and-doc-ledger.md`
