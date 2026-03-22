# ERP Capture 路线注册表

> 本文件由 `scripts/build_erp_capture_route_registry.py` 生成，用来定义“当前账号可见全域路线在 capture 层如何 1:1 落位”。

## 1. 当前目标

- 让所有 `usable_raw_data=true` 的路线在 capture 层都有明确落位，而不是只在文档里停留在“研究过”。
- `capture` 先承担原始留痕与回放职责，`serving` 仍然只接已通过二次准入的路线。
- 这份注册表只回答“怎么落 capture、现在处于什么状态”，不替代 API 成熟度状态板。

## 2. 注册原则

- 所有 usable_raw_data=true 的路线，都必须在 capture 层拥有一条 1:1 的 route 绑定。
- 只有 ready_for_capture_admission 的路线，才允许进入正式 capture 主链。
- reconciliation / research / snapshot 路线可以留痕，但默认不进入 serving 主链。
- 未采纳路线不进入 capture。

## 3. 当前总体状态

- 路线总数：`34`
- 可用原始路线：`28`
- 已确认 capture 路线名：`5`
- 可准入 capture：`4`
- 全域门槛已达成：`是`

按 capture 角色：
- `快照留痕`：`14`
- `主链事实`：`12`
- `不进入 capture`：`6`
- `对账留痕`：`1`
- `研究留痕`：`1`

按当前状态：
- `可选快照留痕`：`14`
- `可准入 capture`：`4`
- `不规划进入 capture`：`6`
- `先继续研究`：`8`
- `仅对账留痕`：`1`
- `仅研究留痕`：`1`

## 4. 路线注册表

| 路线 | 来源分类 | Capture角色 | Capture状态 | Capture Route | 已确认 | route_kind | 参数计划 | Wave | 菜单路径 | 剩余问题 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 库存多维分析 / SelDeptStockAnalysis | 结果快照 | 快照留痕 | 可选快照留痕 | `inventory_seldeptstockanalysis_02d76c57` | 否 | `snapshot` | - | `snapshot_optional` | 报表管理 / 库存报表 / 库存多维分析 | 尚未完成分页/枚举确认 | 补 库存多维分析 的分页/枚举确认，保持结果快照定位 |
| 库存总和分析-按中分类 / SelStockAnalysisList | 结果快照 | 快照留痕 | 可选快照留痕 | `inventory_selstockanalysislist_e06df903` | 否 | `snapshot` | - | `snapshot_optional` | 报表管理 / 库存报表 / 库存综合分析 | 尚未确认是否只保留结果快照定位 | 确认 库存总和分析-按中分类 是否继续只做结果快照 |
| 库存总和分析-按年份季节 / SelStockAnalysisList | 结果快照 | 快照留痕 | 可选快照留痕 | `inventory_selstockanalysislist_bc08e436` | 否 | `snapshot` | - | `snapshot_optional` | 报表管理 / 库存报表 / 库存综合分析 | 尚未确认是否只保留结果快照定位 | 确认 库存总和分析-按年份季节 是否继续只做结果快照 |
| 库存总和分析-按波段 / SelStockAnalysisList | 结果快照 | 快照留痕 | 可选快照留痕 | `inventory_selstockanalysislist_6666bcc9` | 否 | `snapshot` | - | `snapshot_optional` | 报表管理 / 库存报表 / 库存综合分析 | 尚未确认是否只保留结果快照定位 | 确认 库存总和分析-按波段 是否继续只做结果快照 |
| 库存零售统计 / SelDeptStockSaleList | 结果快照 | 快照留痕 | 可选快照留痕 | `inventory_seldeptstocksalelist_5577d06a` | 否 | `snapshot` | - | `snapshot_optional` | 报表管理 / 库存报表 / 库存零售统计 | 尚未完成分页/枚举确认 | 补 库存零售统计 的分页/枚举确认，保持结果快照定位 |
| 日进销存 / SelInSalesReportByDay | 结果快照 | 快照留痕 | 可选快照留痕 | `inventory_selinsalesreportbyday_298fbe2a` | 否 | `snapshot` | - | `snapshot_optional` | 报表管理 / 进出报表 / 日进销存 | 尚未完成分页/枚举确认 | 补 日进销存 的分页/枚举确认，保持结果快照定位 |
| 进销存统计 / SelInSalesReport | 结果快照 | 快照留痕 | 可选快照留痕 | `inventory_selinsalesreport_3f3b23c1` | 否 | `snapshot` | - | `snapshot_optional` | 报表管理 / 进出报表 / 进销存统计 | 尚未完成分页/枚举确认 | 补 进销存统计 的分页/枚举确认，保持结果快照定位 |
| 出入库单据 / SelOutInStockReport | 主源候选 | 主链事实 | 可准入 capture | `inventory_inout_documents` | 是 | `document` | datetype_values=['1', '2']；type_values=['已出库', '已入库', '在途']；doctype_values=['1', '2', '7']；validated_minimum_sweep=True | `wave_2_inventory` | 报表管理 / 进出报表 / 出入库单据 | - | 库存单据已具备 capture 候选准入条件，按最小组合 sweep 进入批次留痕 |
| 库存明细统计 / SelDeptStockWaitList | 主源候选 | 主链事实 | 可准入 capture | `inventory_stock_wait_lines` | 是 | `stock` | stockflag_values=['0', '1']；page_mode=fixed_page_zero | `wave_2_inventory` | 报表管理 / 库存报表 / 库存明细统计 | - | 库存明细统计已具备 capture 候选准入条件，按 stockflag=0/1 双范围留痕并固定 page=0 |
| VIP卡折扣管理 / 待识别 | 未采纳 | 不进入 capture | 不规划进入 capture | `-` | 否 | `excluded` | - | `exclude` | 其他 / VIP卡折扣管理 | 尚未完成单变量探测；尚未完成 HTTP 回证 | 补 VIP卡折扣管理 的单变量探测与 HTTP 回证 |
| 会员总和分析 / SelVipAnalysisReport | 结果快照 | 快照留痕 | 可选快照留痕 | `member_selvipanalysisreport_4f500ec6` | 否 | `snapshot` | - | `snapshot_optional` | 报表管理 / 会员报表 / 会员综合分析 | 尚未完成分页/枚举确认 | 补 会员总和分析 的分页/枚举确认，保持结果快照定位 |
| 会员消费排行 / SelVipSaleRank | 结果快照 | 快照留痕 | 可选快照留痕 | `member_selvipsalerank_ef920c76` | 否 | `snapshot` | - | `snapshot_optional` | 报表管理 / 会员报表 / 会员消费排行 | 尚未完成分页/枚举确认 | 补 会员消费排行 的分页/枚举确认，保持结果快照定位 |
| 会员中心 / SelVipInfoList | 主源候选 | 主链事实 | 先继续研究 | `member_profile_records` | 否 | `raw` | - | `wave_3_member` | 会员资料 / 会员中心 | condition / searchval / VolumeNumber 语义仍待确认；尚未完成纯 HTTP 回证 | 补 condition / searchval / VolumeNumber 的单变量与 HTTP 回证 |
| 会员维护 / 待识别 | 主源候选 | 主链事实 | 先继续研究 | `member_maintenance_records` | 否 | `raw` | - | `wave_3_member` | 会员资料 / 会员维护 | 尚未完成单变量探测；尚未完成 HTTP 回证 | 补 会员维护 的单变量探测与 HTTP 回证 |
| 每日流水单 / SelectRetailDocPaymentSlip | 结果快照 | 快照留痕 | 可选快照留痕 | `daily_payment_slips_snapshot` | 否 | `snapshot` | - | `snapshot_optional` | 报表管理 / 对账报表 / 每日流水单 | SearchType 的完整枚举未确认；尚未确认是否存在分页或数量限制 | 补 SearchType 枚举和分页限制研究，保持结果快照定位 |
| 收货确认 / GetViewGridList | 主源候选 | 主链事实 | 先继续研究 | `receipt_confirmation_documents` | 否 | `raw` | - | `wave_3_payment_and_docs` | 单据管理 / 上级往来 / 收货确认 | 尚未完成单变量探测；尚未完成 HTTP 回证 | 补 收货确认 的单变量探测与 HTTP 回证 |
| 退货明细 / GetViewGridList | 主源候选 | 主链事实 | 先继续研究 | `return_document_lines` | 否 | `raw` | - | `wave_3_payment_and_docs` | 报表管理 / 进出报表 / 退货明细 | 尚未完成单变量探测；尚未完成 HTTP 回证 | 补 退货明细 的单变量探测与 HTTP 回证 |
| 门店盘点单 / GetViewGridList | 主源候选 | 主链事实 | 先继续研究 | `store_stocktaking_documents` | 否 | `raw` | - | `wave_3_payment_and_docs` | 单据管理 / 盘点业务 / 门店盘点单 | 尚未完成单变量探测；尚未完成 HTTP 回证 | 补 门店盘点单 的单变量探测与 HTTP 回证 |
| 参数设置 / page_baseline | 未采纳 | 不进入 capture | 不规划进入 capture | `-` | 否 | `excluded` | - | `exclude` | 其他 / 参数设置 | 配置/设置类页面，默认不进入事实主链 | 保持 参数设置 为未采纳；若后续确认有长期分析价值，再单独评估 snapshot 路线 |
| 导购员设置 / page_baseline | 未采纳 | 不进入 capture | 不规划进入 capture | `-` | 否 | `excluded` | - | `exclude` | 其他 / 导购员设置 | 配置/设置类页面，默认不进入事实主链 | 保持 导购员设置 为未采纳；若后续确认有长期分析价值，再单独评估 snapshot 路线 |
| 小票设置 / page_baseline | 未采纳 | 不进入 capture | 不规划进入 capture | `-` | 否 | `excluded` | - | `exclude` | 其他 / 小票设置 | 配置/设置类页面，默认不进入事实主链 | 保持 小票设置 为未采纳；若后续确认有长期分析价值，再单独评估 snapshot 路线 |
| 店铺定位 / GetControlData | 未采纳 | 不进入 capture | 不规划进入 capture | `-` | 否 | `excluded` | - | `exclude` | 其他 / 店铺定位 | 配置/设置类页面，默认不进入事实主链 | 保持 店铺定位 为未采纳；若后续确认有长期分析价值，再单独评估 snapshot 路线 |
| 店铺零售清单 / GetDIYReportData | 未采纳 | 不进入 capture | 不规划进入 capture | `-` | 否 | `excluded` | - | `exclude` | 报表管理 / 零售报表 / 店铺零售清单 | 尚未完成单变量探测；尚未完成 HTTP 回证 | 补 店铺零售清单 的单变量探测与 HTTP 回证 |
| SelDeptSaleList | 对账源 | 对账留痕 | 仅对账留痕 | `sales_reconciliation_detail_stats` | 否 | `reconciliation` | - | `research_only` | 报表管理 / 零售报表 / 零售明细统计 | - | 保持研究/对账源定位，补充极端单日窗口的 edge case 说明即可 |
| sales_reverse_document_lines | 研究留痕 | 研究留痕 | 仅研究留痕 | `sales_reverse_document_lines` | 是 | `reverse` | - | `research_only` | 报表管理 / 零售报表 / 销售清单 | - | 继续保持 capture 研究留痕，不进入 serving 或 dashboard 主链 |
| 商品销售情况 / SelSaleReportData | 结果快照 | 快照留痕 | 可选快照留痕 | `sales_selsalereportdata_27b606d5` | 否 | `snapshot` | - | `snapshot_optional` | 报表管理 / 综合分析 / 商品销售情况 | 尚未完成分页/枚举确认 | 补 商品销售情况 的分页/枚举确认，保持结果快照定位 |
| 门店销售月报 / DeptMonthSalesReport | 结果快照 | 快照留痕 | 可选快照留痕 | `sales_deptmonthsalesreport_e660cf50` | 否 | `snapshot` | - | `snapshot_optional` | 报表管理 / 综合分析 / 门店销售月报 | 尚未完成分页/枚举确认 | 补 门店销售月报 的分页/枚举确认，保持结果快照定位 |
| GetDIYReportData(E004001008_2) | 主源候选 | 主链事实 | 可准入 capture | `sales_document_lines` | 是 | `line` | - | `wave_1_sales` | 报表管理 / 零售报表 / 销售清单 | - | 已可按 sale_no 分流正常明细与逆向明细，准备首批 capture 准入 |
| SelSaleReport | 主源候选 | 主链事实 | 可准入 capture | `sales_documents_head` | 是 | `head` | - | `wave_1_sales` | 报表管理 / 零售报表 / 销售清单 | - | 已具备首批 capture 准入条件，保持 serving 冻结并先观测批次回归指标 |
| 商品资料 / 待识别 | 主源候选 | 主链事实 | 先继续研究 | `sales_route_bd7dc3de` | 否 | `raw` | - | `wave_1_sales` | 基础资料 / 商品资料 | 尚未完成单变量探测；尚未完成 HTTP 回证 | 补 商品资料 的单变量探测与 HTTP 回证 |
| 客户资料 / GetControlData | 主源候选 | 主链事实 | 先继续研究 | `customer_master_records` | 否 | `raw` | - | `wave_1_sales` | 基础资料 / 客户资料 | 尚未完成单变量探测；尚未完成 HTTP 回证 | 补 客户资料 的单变量探测与 HTTP 回证 |
| 储值卡汇总 / GetDIYReportData | 结果快照 | 快照留痕 | 可选快照留痕 | `stored_value_route_5180a5fa` | 否 | `snapshot` | - | `snapshot_optional` | 报表管理 / 会员报表 / 储值卡汇总 | 尚未完成分页/枚举确认 | 补 储值卡汇总 的分页/枚举确认，保持结果快照定位 |
| 储值按店汇总 / GetDIYReportData | 结果快照 | 快照留痕 | 可选快照留痕 | `stored_value_route_3e94fbcb` | 否 | `snapshot` | - | `snapshot_optional` | 报表管理 / 会员报表 / 储值按店汇总 | 尚未完成分页/枚举确认 | 补 储值按店汇总 的分页/枚举确认，保持结果快照定位 |
| 储值卡明细 / GetDIYReportData | 主源候选 | 主链事实 | 先继续研究 | `stored_value_card_detail` | 否 | `raw` | - | `wave_3_stored_value` | 报表管理 / 会员报表 / 储值卡明细 | Search 语义仍待确认；尚未确认是否存在隐藏分页或服务端上限 | 先补 Search 语义与分页上限验证，再评估储值域主源准入 |

## 5. Wave Blocker 摘要

### `snapshot_optional`

- `10` 次：尚未完成分页/枚举确认
- `3` 次：尚未确认是否只保留结果快照定位
- `1` 次：SearchType 的完整枚举未确认
- `1` 次：尚未确认是否存在分页或数量限制

### `exclude`

- `4` 次：配置/设置类页面，默认不进入事实主链
- `2` 次：尚未完成单变量探测
- `2` 次：尚未完成 HTTP 回证

### `wave_3_member`

- `1` 次：condition / searchval / VolumeNumber 语义仍待确认
- `1` 次：尚未完成纯 HTTP 回证
- `1` 次：尚未完成单变量探测
- `1` 次：尚未完成 HTTP 回证

### `wave_3_payment_and_docs`

- `3` 次：尚未完成单变量探测
- `3` 次：尚未完成 HTTP 回证

### `wave_1_sales`

- `2` 次：尚未完成单变量探测
- `2` 次：尚未完成 HTTP 回证

### `wave_3_stored_value`

- `1` 次：Search 语义仍待确认
- `1` 次：尚未确认是否存在隐藏分页或服务端上限
