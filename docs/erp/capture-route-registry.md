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

- 路线总数：`35`
- 可用原始路线：`29`
- 已确认 capture 路线名：`18`
- 可准入 capture：`11`
- 已真实写入 capture：`20`
- 仍阻塞的主链候选：`1`
- 全域门槛已达成：`是`

按 capture 角色：
- `快照留痕`：`14`
- `主链事实`：`12`
- `不进入 capture`：`6`
- `研究留痕`：`2`
- `对账留痕`：`1`

按当前状态：
- `可选快照留痕`：`14`
- `可准入 capture`：`11`
- `不规划进入 capture`：`6`
- `仅研究留痕`：`2`
- `候选但阻塞`：`1`
- `仅对账留痕`：`1`

当前仍阻塞的主链候选：
- `退货明细 / SelReturnStockList`

## 4. 路线注册表

| 路线 | 来源分类 | Capture角色 | Capture状态 | Capture Route | 已确认 | route_kind | 已写capture | 最新batch | 参数计划 | Wave | 菜单路径 | 剩余问题 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 库存多维分析 / SelDeptStockAnalysis | 结果快照 | 快照留痕 | 可选快照留痕 | `inventory_seldeptstockanalysis_02d76c57` | 否 | `snapshot` | 否 | `-` | - | `snapshot_optional` | 报表管理 / 库存报表 / 库存多维分析 | 尚未完成分页/枚举确认 | 补 库存多维分析 的分页/枚举确认，保持结果快照定位 |
| 库存总和分析-按中分类 / SelStockAnalysisList | 结果快照 | 快照留痕 | 可选快照留痕 | `inventory_selstockanalysislist_e06df903` | 否 | `snapshot` | 否 | `-` | - | `snapshot_optional` | 报表管理 / 库存报表 / 库存综合分析 | 尚未确认是否只保留结果快照定位 | 确认 库存总和分析-按中分类 是否继续只做结果快照 |
| 库存总和分析-按年份季节 / SelStockAnalysisList | 结果快照 | 快照留痕 | 可选快照留痕 | `inventory_selstockanalysislist_bc08e436` | 否 | `snapshot` | 否 | `-` | - | `snapshot_optional` | 报表管理 / 库存报表 / 库存综合分析 | 尚未确认是否只保留结果快照定位 | 确认 库存总和分析-按年份季节 是否继续只做结果快照 |
| 库存总和分析-按波段 / SelStockAnalysisList | 结果快照 | 快照留痕 | 可选快照留痕 | `inventory_selstockanalysislist_6666bcc9` | 否 | `snapshot` | 否 | `-` | - | `snapshot_optional` | 报表管理 / 库存报表 / 库存综合分析 | 尚未确认是否只保留结果快照定位 | 确认 库存总和分析-按波段 是否继续只做结果快照 |
| 库存零售统计 / SelDeptStockSaleList | 结果快照 | 快照留痕 | 可选快照留痕 | `inventory_seldeptstocksalelist_5577d06a` | 否 | `snapshot` | 否 | `-` | - | `snapshot_optional` | 报表管理 / 库存报表 / 库存零售统计 | 尚未完成分页/枚举确认 | 补 库存零售统计 的分页/枚举确认，保持结果快照定位 |
| 日进销存 / SelInSalesReportByDay | 结果快照 | 快照留痕 | 可选快照留痕 | `inventory_selinsalesreportbyday_298fbe2a` | 否 | `snapshot` | 否 | `-` | - | `snapshot_optional` | 报表管理 / 进出报表 / 日进销存 | 尚未完成分页/枚举确认 | 补 日进销存 的分页/枚举确认，保持结果快照定位 |
| 进销存统计 / SelInSalesReport | 结果快照 | 快照留痕 | 可选快照留痕 | `inventory_selinsalesreport_3f3b23c1` | 否 | `snapshot` | 否 | `-` | - | `snapshot_optional` | 报表管理 / 进出报表 / 进销存统计 | 尚未完成分页/枚举确认 | 补 进销存统计 的分页/枚举确认，保持结果快照定位 |
| 出入库单据 / SelOutInStockReport | 主源候选 | 主链事实 | 可准入 capture | `inventory_inout_documents` | 是 | `document` | 是 | `d5e1b38acc814a68b17c64652eba405f` | datetype_values=['1', '2']；type_values=['已出库', '已入库', '在途']；doctype_values=['1', '2', '7']；validated_minimum_sweep=True | `wave_2_inventory` | 报表管理 / 进出报表 / 出入库单据 | - | 已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。 |
| 库存明细统计 / SelDeptStockWaitList | 主源候选 | 主链事实 | 可准入 capture | `inventory_stock_wait_lines` | 是 | `stock` | 是 | `93b8fa4252c345b190de5b2b2751c391` | stockflag_values=['0', '1']；page_mode=fixed_page_zero | `wave_2_inventory` | 报表管理 / 库存报表 / 库存明细统计 | - | 已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。 |
| VIP卡折扣管理 / 待识别 | 未采纳 | 不进入 capture | 不规划进入 capture | `-` | 否 | `excluded` | 否 | `-` | - | `exclude` | 其他 / VIP卡折扣管理 | 尚未完成单变量探测；尚未完成 HTTP 回证 | 补 VIP卡折扣管理 的单变量探测与 HTTP 回证 |
| 会员总和分析 / SelVipAnalysisReport | 结果快照 | 快照留痕 | 可选快照留痕 | `member_analysis_snapshot_records` | 是 | `snapshot` | 是 | `4690b28a62fb404881624040b8c75f93` | default_salebdate=20250301；default_saleedate=20250401；default_birthbdate=；default_birthedate=；default_type=；default_tag=；default_page=0；default_pagesize=0；request_keys=['birthbdate', 'birthedate', 'page', 'pagesize', 'salebdate', 'saleedate', 'salemoney1', 'salemoney2', 'tag', 'type']；page_mode=page_zero_full_fetch；observed_total_rows=25；page_probe_results={'page_0_pagesize_20_rows': 25, 'page_1_pagesize_20_rows': 20, 'page_1_pagesize_0_rows': 25}；type_semantics={'tested_values': ['blank', '1', '2', '3'], 'same_dataset_values': ['1', '2', '3', 'blank'], 'different_dataset_values': [], 'error_values': [], 'same_dataset_for_tested_values': True}；tag_semantics={'tested_values': ['blank', '1', '2', '3'], 'same_dataset_values': ['blank'], 'different_dataset_values': ['1', '2', '3'], 'error_values': [], 'same_dataset_for_tested_values': False} | `snapshot_optional` | 报表管理 / 会员报表 / 会员综合分析 | - | 会员总和分析已满足 snapshot capture 条件；按 page=0 单请求写入 capture，并继续保持结果快照定位。 |
| 会员消费排行 / SelVipSaleRank | 结果快照 | 快照留痕 | 可选快照留痕 | `member_sales_rank_snapshot_records` | 是 | `snapshot` | 是 | `9c9f0548cb724672a218cbbe7af8acc9` | default_bdate=20250301；default_edate=20260401；default_page=0；default_pagesize=0；request_keys=['bdate', 'edate', 'page', 'pagesize']；page_mode=page_zero_full_fetch；declared_total_count=1204；observed_total_rows=1204；single_request_complete=True；page_probe_results={'page_0_pagesize_20_rows': 1204, 'page_1_pagesize_20_rows': 20, 'page_1_pagesize_0_rows': 1204} | `snapshot_optional` | 报表管理 / 会员报表 / 会员消费排行 | - | 会员消费排行已满足 snapshot capture 条件；按 page=0 单请求写入 capture，并继续保持排行快照定位。 |
| 会员中心 / SelVipInfoList | 主源候选 | 主链事实 | 可准入 capture | `member_profile_records` | 否 | `raw` | 是 | `38ae72ea2f5344c399c59409d51517b8` | default_condition=；default_searchval=；default_VolumeNumber=；search_mode=global_filter_when_condition_empty；search_exact_examples=['exact_search']；volume_examples=['1', '2', '10'] | `wave_3_member` | 会员资料 / 会员中心 | - | 已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。 |
| 会员维护 / SelVipReturnVisitList | 主源候选 | 主链事实 | 可准入 capture | `member_maintenance_records` | 是 | `master` | 是 | `c26d550fa8ea49aa8c40b34fb3e95073` | default_search=；default_type=；default_bdate=；default_edate=；default_brdate=；default_erdate=；baseline_page=1；baseline_pagesize=20；page_seed_values=['page=2,pagesize=20', 'page=3,pagesize=20']；pagesize_seed_values=['page=1,pagesize=50', 'page=1,pagesize=5000']；search_seed_values=['__no_match__', 'blank']；type_seed_values=['消费回访', '其他回访']；bdate_seed_values=['bdate=20260323,edate=20260323', 'bdate=20260301,edate=20260323']；brdate_seed_values=['brdate=20260323,erdate=20260323', 'brdate=20260301,erdate=20260323']；page_mode=single_request_stable_empty_verified；empty_dataset_confirmed=True | `wave_3_member` | 会员资料 / 会员维护 | - | 已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。 |
| 门店盘点单 / store_stocktaking_diff_records | 研究留痕 | 研究留痕 | 仅研究留痕 | `store_stocktaking_diff_records` | 是 | `diff` | 是 | `5a1206e4be9340359e9a8b0ed14433e0` | trigger_method=getDiffData(row)；selected_row_required=True；observed_order_diff_rows=20；observed_order_diff_summary_rows=2；multi_row_supported=False | `research_only` | 单据管理 / 盘点业务 / 门店盘点单 | 统计损溢当前更像本地派生数据，尚未确认独立 HTTP route；尚未确认多单据场景下 orderDiffData 是否稳定；按行调用 getDiffData(row_1) 当前会把 diff 状态清空，尚未证明多行稳定；按行调用 getDiffData(row_2) 当前仍未拿到稳定选中行 | 继续区分默认 getDiffData() 产出的损溢总表与按行 getDiffData(row) 的稳定性，再决定是否把本地损溢数据固定为长期二级 raw route。 |
| 每日流水单 / SelectRetailDocPaymentSlip | 结果快照 | 快照留痕 | 可选快照留痕 | `daily_payment_slips_snapshot` | 是 | `snapshot` | 是 | `ff538d7129f74e8288023fc991618aab` | default_menu_id=E004006001；default_search_type=1；default_search=；default_last_date=；default_begin_date=2025-03-01；default_end_date=2026-04-01；request_keys=['BeginDate', 'EndDate', 'LastDate', 'MenuID', 'Search', 'SearchType']；page_mode=single_request_no_pagination_fields；observed_total_rows=4045；searchtype_semantics={'tested_values': ['', '1', '2', '3', '4', '5'], 'same_dataset_values': ['', '1', '2', '3', '4', '5'], 'different_dataset_values': [], 'error_values': [], 'same_dataset_for_tested_values': True} | `snapshot_optional` | 报表管理 / 对账报表 / 每日流水单 | - | 每日流水单已满足 snapshot capture 条件；按默认窗口单请求写入 capture，并继续保持结果快照定位。 |
| 收货确认 / SelDocConfirmList | 主源候选 | 主链事实 | 可准入 capture | `receipt_confirmation_documents` | 是 | `document` | 是 | `4f61becdb09342cda68916c5b39f38b8` | baseline_payload={}；page_seed_values=['page=1,pagesize=20', 'page=2,pagesize=20']；page_size_seed_values=['page=1,pagesize=20', 'page=1,pagesize=5000']；time_seed_values=['time=20260323', "time=''"]；search_seed_values=['__no_match__', 'search=PFD-A019-014903']；page_mode=single_request_same_dataset_verified；time_mode=keep_default_empty_payload；search_mode=ignored_for_primary_list；secondary_actions_pending=['单据确认', '物流信息', '扫描校验'] | `wave_3_payment_and_docs` | 单据管理 / 上级往来 / 收货确认 | - | 收货确认主列表已 admit；下一步应沿 receiveConfirm.menuId、父链 menuItemId.CheckDoc 与 detailData.currentItem 的断点继续回溯更早的上游数据注入点，并追 RTM_reportTable.props.tableData、allTableData/vxeTable.tableData、vxeTable.database 与 FXDATABASE/receiveConfirm_E003001001_1 本地表初始化的来源，确认为何 receiveConfirm / reportTableItem_mainRef / RTM_reportTable 三层都有分页状态却始终没有行数据。 |
| 退货明细 / SelReturnStockList | 主源候选 | 主链事实 | 候选但阻塞 | `return_document_lines` | 否 | `raw` | 是 | `1eb5e37d3f5643e08eaacdfc3b504dfa` | baseline_payload={'menuid': 'E004003004', 'gridid': 'E004003004_2', 'warecause': '', 'spenum': ''}；type_seed_values=['blank', '0', '1', '2', '3', '4', '5']；successful_type_values=[]；narrow_filter_seed_values=['TrademarkCode=01', 'Years=2026', 'Season=1', 'PlatId=1', 'Order=1', 'ArriveStore=1', 'TrademarkCode=01,Years=2026', '品牌(TrademarkCode)=01', '年份(Years)=2026', '季节(Season)=1', '大类(TypeCode)=04', '中类(TypeCode)=0403', '小类(TypeCode)=040301', '波段(State)=1a', '上架模式(PlatId)=1', '订单来源(Order)=1', '提货方式(ArriveStore)=1', '小类(TypeCode)=040301,品牌(TrademarkCode)=01', '小类(TypeCode)=040301,年份(Years)=2026', '小类(TypeCode)=040301,季节(Season)=1', '小类(TypeCode)=040301,波段(State)=1a', '小类(TypeCode)=040301,上架模式(PlatId)=1', '小类(TypeCode)=040301,订单来源(Order)=1', '小类(TypeCode)=040301,提货方式(ArriveStore)=1']；page_mode=not_applicable_yet | `wave_3_payment_and_docs` | 报表管理 / 进出报表 / 退货明细 | 当前 seed type 值全部触发服务端错误；服务端 SQL 截断错误仍未解除；尚未确认可稳定返回数据的 type 取值；已验证的窄过滤 seed 仍全部触发服务端错误；已补测祖先状态暴露的 type=4/5 候选值，仍全部触发服务端错误；ReturnStockBaseInfo 当前 11 个可见筛选维度都已纳入 probe，问题已不在可见筛选遗漏；页面真实点击后的查询请求仍未改变 post body；组件诊断仍未暴露 route-level 过滤模型；已定位 RTM_searchConditions/RTM_getReportInfo，但调用后仍未触发新请求；RTM_reportTable 目前只暴露方法与 vxeTable 空条件状态，仍未看到可写筛选模型；RTM_searchConditions/RTM_getReportInfo 当前只暴露 native code 包装，仍无法从函数体反推出隐藏上下文；RTM_reportTable.vxeTable.database 已指向 FXDATABASE，但浏览器实际打开后 object_store_names 为空，salesReturnDetailReport 并未落成本地表；RTM_reportTable.searchConditions/searchDataInfo/pageCondition/getReportInfo/conditionStr 当前都只暴露 native code 包装；salesReturnDetailReport 根组件的查询/加载方法当前也只暴露 native code 包装，无法继续从根组件函数体反推上下文注入链；salesReturnDetailReport 父链壳层方法当前也只暴露 native code 包装，说明更早的菜单/页面注入链同样不可从函数体继续回溯；salesReturnDetail 自身 ref 当前只拿到 showLoading 回调，父链 navmenu 也未见任何附加数据载荷，说明壳层 ref 仍不是缺失退货数据的来源；store/root 当前只见 cleardata=false 与空 root_data_snapshot，仍未见任何退货数据缓存；localStorage/sessionStorage/window 当前只见登录态与通用字段，salesReturnDetailReport.vm 的 databaseTableName 仍为空；route/parent 注入上下文当前只有 menuItemId/reportLists 等壳层信息，未见额外退货查询参数 | 页面默认 payload、type seed 和已验证窄过滤仍全部报错；下一步应优先定位页面动作链或服务端字段边界，而不是继续盲加基础过滤 |
| 门店盘点单 / SelDocManageList | 主源候选 | 主链事实 | 可准入 capture | `store_stocktaking_documents` | 是 | `document` | 是 | `2f31764d5f414aba9af48fb7577faddf` | baseline_payload={'edate': '20260323', 'bdate': '20260316', 'deptcode': '', 'stat': 'A', 'menuid': 'E003002001'}；stat_seed_values=['stat=A', 'stat=0', 'stat=1']；primary_stat_values=['A', '1']；equivalent_stat_values=['stat=1']；excluded_stat_values=['stat=0']；date_seed_values=['bdate=20260316,edate=20260323', 'bdate=20260323,edate=20260323']；page_mode=no_pagination_field_observed；date_window_mode=fixed_bdate_edate_window；secondary_actions_pending=['查看明细', '统计损溢', '条码记录'] | `wave_3_payment_and_docs` | 单据管理 / 盘点业务 / 门店盘点单 | - | 门店盘点单主列表已可准入 capture；下一步应优先确认 getDiffData(row) 产出的本地损溢数据是否可作为二级 raw route，再决定是否继续追独立 HTTP 接口。 |
| 参数设置 / page_baseline | 未采纳 | 不进入 capture | 不规划进入 capture | `-` | 否 | `excluded` | 否 | `-` | - | `exclude` | 其他 / 参数设置 | 配置/设置类页面，默认不进入事实主链 | 保持 参数设置 为未采纳；若后续确认有长期分析价值，再单独评估 snapshot 路线 |
| 导购员设置 / page_baseline | 未采纳 | 不进入 capture | 不规划进入 capture | `-` | 否 | `excluded` | 否 | `-` | - | `exclude` | 其他 / 导购员设置 | 配置/设置类页面，默认不进入事实主链 | 保持 导购员设置 为未采纳；若后续确认有长期分析价值，再单独评估 snapshot 路线 |
| 小票设置 / page_baseline | 未采纳 | 不进入 capture | 不规划进入 capture | `-` | 否 | `excluded` | 否 | `-` | - | `exclude` | 其他 / 小票设置 | 配置/设置类页面，默认不进入事实主链 | 保持 小票设置 为未采纳；若后续确认有长期分析价值，再单独评估 snapshot 路线 |
| 店铺定位 / GetControlData | 未采纳 | 不进入 capture | 不规划进入 capture | `-` | 否 | `excluded` | 否 | `-` | - | `exclude` | 其他 / 店铺定位 | 配置/设置类页面，默认不进入事实主链 | 保持 店铺定位 为未采纳；若后续确认有长期分析价值，再单独评估 snapshot 路线 |
| 店铺零售清单 / GetDIYReportData | 未采纳 | 不进入 capture | 不规划进入 capture | `-` | 否 | `excluded` | 否 | `-` | - | `exclude` | 报表管理 / 零售报表 / 店铺零售清单 | 尚未完成单变量探测；尚未完成 HTTP 回证 | 补 店铺零售清单 的单变量探测与 HTTP 回证 |
| SelDeptSaleList | 对账源 | 对账留痕 | 仅对账留痕 | `sales_reconciliation_detail_stats` | 否 | `reconciliation` | 否 | `-` | - | `research_only` | 报表管理 / 零售报表 / 零售明细统计 | - | 保持研究/对账源定位，补充极端单日窗口的 edge case 说明即可 |
| sales_reverse_document_lines | 研究留痕 | 研究留痕 | 仅研究留痕 | `sales_reverse_document_lines` | 是 | `reverse` | 是 | `7d361ed0079f4584871996db0cf721e5` | - | `research_only` | 报表管理 / 零售报表 / 销售清单 | - | 继续保持 capture 研究留痕，不进入 serving 或 dashboard 主链 |
| 商品销售情况 / SelSaleReportData | 结果快照 | 快照留痕 | 可选快照留痕 | `product_sales_snapshot_records` | 是 | `snapshot` | 是 | `6dc6fa6f416345639f9b41a41fceeb42` | default_bdate=20250301；default_edate=20260401；default_warecause=；default_spenum=；request_keys=['bdate', 'edate', 'spenum', 'warecause']；page_mode=single_request_declared_total_match；declared_total_count=1356；observed_total_rows=1356；single_request_complete=True | `snapshot_optional` | 报表管理 / 综合分析 / 商品销售情况 | - | 商品销售情况已满足 snapshot capture 条件；按默认时间窗单请求写入 capture，并继续保持结果快照定位。 |
| 门店销售月报 / DeptMonthSalesReport | 结果快照 | 快照留痕 | 可选快照留痕 | `sales_deptmonthsalesreport_e660cf50` | 否 | `snapshot` | 否 | `-` | - | `snapshot_optional` | 报表管理 / 综合分析 / 门店销售月报 | 尚未完成分页/枚举确认 | 补 门店销售月报 的分页/枚举确认，保持结果快照定位 |
| GetDIYReportData(E004001008_2) | 主源候选 | 主链事实 | 可准入 capture | `sales_document_lines` | 是 | `line` | 是 | `7d361ed0079f4584871996db0cf721e5` | - | `wave_1_sales` | 报表管理 / 零售报表 / 销售清单 | - | 已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。 |
| SelSaleReport | 主源候选 | 主链事实 | 可准入 capture | `sales_documents_head` | 是 | `head` | 是 | `7d361ed0079f4584871996db0cf721e5` | - | `wave_1_sales` | 报表管理 / 零售报表 / 销售清单 | - | 已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。 |
| 商品资料 / SelWareList | 主源候选 | 主链事实 | 可准入 capture | `product_master_records` | 是 | `master` | 是 | `453246095da848939df0c7f2768f9b0c` | default_spenum=；default_warecause=；baseline_page=1；recommended_pagesize=5000；page_mode=sequential_pagination；full_capture_with_empty_warecause=True；exact_search_examples=['TMX1B90549A', 'TMX1B90550A', 'TMX1B90540A']；broad_search_examples=['TN', 'TOX1'] | `wave_1_sales` | 基础资料 / 商品资料 | - | 已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。 |
| 客户资料 / SelDeptList | 主源候选 | 主链事实 | 可准入 capture | `customer_master_records` | 是 | `master` | 是 | `65eb6cbf325d4cccb610c91b3fd0ef5b` | default_deptname=；baseline_page=1；baseline_pagesize=20；page_seed_values=['page=2,pagesize=20', 'page=3,pagesize=20']；pagesize_seed_values=['page=1,pagesize=50', 'page=1,pagesize=5000']；deptname_seed_values=['__no_match__', 'blank']；page_mode=single_request_stable_empty_verified；empty_dataset_confirmed=True | `wave_1_sales` | 基础资料 / 客户资料 | - | 已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。 |
| 储值卡汇总 / GetDIYReportData | 结果快照 | 快照留痕 | 可选快照留痕 | `stored_value_card_summary_snapshot_records` | 是 | `snapshot` | 是 | `ef07a37eec634b239efbe43987949670` | default_menuid=E004004004；default_gridid=E004004004_main；default_begin_date=2025-03-01；default_end_date=2026-04-01；default_search=；request_keys=['gridid', 'menuid', 'parameter']；parameter_keys=['BeginDate', 'EndDate', 'Search']；page_mode=single_request_page_field_ignored；declared_total_count=None；observed_total_rows=19；single_request_complete=True；page_probe_results={'page_0_pagesize_20_rows': 19, 'page_1_pagesize_20_rows': 19, 'page_1_pagesize_0_rows': 19}；search_semantics={'tested_values': ['__no_match__'], 'same_dataset_values': [], 'different_dataset_values': ['__no_match__'], 'error_values': []} | `snapshot_optional` | 报表管理 / 会员报表 / 储值卡汇总 | - | 储值卡汇总已满足 snapshot capture 条件；按默认 Search 空值单请求写入 capture，并继续保持卡级汇总快照定位。 |
| 储值按店汇总 / GetDIYReportData | 结果快照 | 快照留痕 | 可选快照留痕 | `stored_value_by_store_snapshot_records` | 是 | `snapshot` | 是 | `97a609b7e3a04043be42095ccf114157` | default_menuid=E004004003；default_gridid=E004004003_main；default_begin_date=2025-03-01；default_end_date=2026-04-01；request_keys=['gridid', 'menuid', 'parameter']；parameter_keys=['BeginDate', 'EndDate']；page_mode=single_request_page_field_ignored；declared_total_count=None；observed_total_rows=1；single_request_complete=True；page_probe_results={'page_0_pagesize_20_rows': 1, 'page_1_pagesize_20_rows': 1, 'page_1_pagesize_0_rows': 1} | `snapshot_optional` | 报表管理 / 会员报表 / 储值按店汇总 | - | 储值按店汇总已满足 snapshot capture 条件；按默认时间窗单请求写入 capture，并继续保持门店级汇总快照定位。 |
| 储值卡明细 / GetDIYReportData | 主源候选 | 主链事实 | 可准入 capture | `stored_value_card_detail` | 是 | `detail` | 是 | `fa278535105e40529fa9c0020966b70a` | default_BeginDate=2025-03-01；default_EndDate=2026-04-01；default_Search=；search_mode=vip_card_only_filter；page_mode=single_request_half_open_date_verified；date_boundary_mode=half_open_end_date；search_seed_examples=['__no_match__', 'vip_card_id:18797319891', 'vip_card_id:18892055896', 'vip_card_id:18991007010', 'happen_no:A000002904', 'happen_no:A000003322', 'happen_no:20250905142254', 'vip_name:毛豆', 'vip_name:有米', 'vip_name:窦慕兰'] | `wave_3_stored_value` | 报表管理 / 会员报表 / 储值卡明细 | - | 已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。 |

## 5. Wave Blocker 摘要

### `snapshot_optional`

- `5` 次：尚未完成分页/枚举确认
- `3` 次：尚未确认是否只保留结果快照定位

### `exclude`

- `4` 次：配置/设置类页面，默认不进入事实主链
- `2` 次：尚未完成单变量探测
- `2` 次：尚未完成 HTTP 回证

### `research_only`

- `1` 次：统计损溢当前更像本地派生数据，尚未确认独立 HTTP route
- `1` 次：尚未确认多单据场景下 orderDiffData 是否稳定
- `1` 次：按行调用 getDiffData(row_1) 当前会把 diff 状态清空，尚未证明多行稳定
- `1` 次：按行调用 getDiffData(row_2) 当前仍未拿到稳定选中行

### `wave_3_payment_and_docs`

- `1` 次：当前 seed type 值全部触发服务端错误
- `1` 次：服务端 SQL 截断错误仍未解除
- `1` 次：尚未确认可稳定返回数据的 type 取值
- `1` 次：已验证的窄过滤 seed 仍全部触发服务端错误
- `1` 次：已补测祖先状态暴露的 type=4/5 候选值，仍全部触发服务端错误
