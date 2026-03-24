# 流水与单据域接口台账

## 1. 当前目标

这一域主要承接：

- 支付流水
- 单据级查询
- 与日常经营核对有关的结果视图

---

## 2. 接口总表

| 页面/报表 | endpoint | method | 认证方式 | 主要过滤字段 | 当前判断 | 风险标签 | 抓取策略 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 每日流水单 | `JyApi/ReconciliationAnalysis/SelectRetailDocPaymentSlip` | `POST` | `Authorization` | `MenuID` `SearchType` `Search` `LastDate` `BeginDate` `EndDate` | 支付流水结果接口；最新 HTTP evidence 已确认默认窗口单请求稳定返回 `4045` 行，且 `SearchType=blank/1/2/3/4/5` 当前仍是同一数据集，可作为 snapshot capture 留痕 | 结果快照 | 单请求快照 |
| 出入库单据 | `YisEposReport/SelOutInStockReport` | `POST` | `token` | `bdate` `edate` `datetype` `type` `doctype` `spenum` `warecause` `page` `pagesize` | 单据明细候选，和库存域强相关 | 需要扫枚举 | 自动翻页 |
| 门店销售月报 | `JyApi/DeptMonthSalesReport/DeptMonthSalesReport` | `POST` | `Authorization` | `Type` `BeginDate` `EndDate` `YBeginDate` `YEndDate` `MBeginDate` `MEndDate` `PageIndex` `PageSize` | 经营月报结果视图 | 需要翻页 | 结果快照 |
| 退货明细 | `YisEposReport/SelReturnStockList` | `POST` | `token` | `menuid` `gridid` `warecause` `spenum` `type` 及 `ReturnStockBaseInfo` 派生维度 | 当前真实数据接口已识别，但页面默认请求、`type` seed、基于 `ReturnStockBaseInfo` 派生的品牌/年份/季节/类别/波段/上架模式/订单来源/提货方式过滤，以及页面真实点击后的查询请求，都仍落回同一 payload 并触发 SQL 截断。最新补测还确认：`ReturnStockBaseInfo` 当前 11 个可见筛选维度都已纳入 probe，且祖先状态里暴露的 `type=4/5` 候选值也同样全部报错。进一步的 UI probe 已定位到 `salesReturnDetailReport` 组件及其 `RTM_searchConditions / RTM_getReportInfo` 方法，但调用后仍不发新请求；最新 ref/IndexedDB 取证又确认 `RTM_reportTable` 也挂在 `FXDATABASE` 本地库链上，不过浏览器实际打开后 `object_store_names` 仍为空，目标表 `salesReturnDetailReport` 并未落成本地表；同时 `RTM_reportTable.searchConditions/searchDataInfo/pageCondition/getReportInfo/conditionStr` 这些关键方法当前也都只暴露 `native code` 包装。最新父链方法取证进一步确认：不仅 `salesReturnDetailReport` 根组件的查询/加载方法全部是 `native code` 包装，连上一层壳组件的 `GetMenuList/getPermission/getMessage` 等方法也都只暴露 `native code` 包装，说明更早的菜单/页面注入链同样不可从函数体继续回溯；而新增 ancestry ref probe 还确认 `salesReturnDetail` 自身 ref 现在只拿到 `showLoading` 回调，父链 `navmenu` 也没有任何附加数据载荷，所以壳层 ref 也不是缺失退货数据的来源，暂不能准入主链 | 服务端错误；页面筛选当前未改变 post body；组件方法已定位但仍不触发请求；`RTM_searchConditions / RTM_getReportInfo` 当前只暴露 `native code` 包装；`RTM_reportTable` 只见方法与空条件状态，仍未定位到真正的退货筛选模型；`RTM_reportTable.vxeTable.database` 虽指向 `FXDATABASE`，但目标表 `salesReturnDetailReport` 仍未落成本地表；根组件与父链壳层方法也都只暴露 `native code` 包装；壳层 ref 仍未见附加载荷；可见筛选维度已全部纳入 probe；`type=4/5` 也已排除；需确认隐藏上下文或服务端边界 | 待识别 |
| 收货确认 | `JyApi/EposDoc/SelDocConfirmList` | `POST` | `Authorization` | `page` `pageSize` `time` `search` | 当前真实主列表接口已识别并完成 HTTP 回证；主列表已可按空 payload 准入 capture。最新 UI probe 与组件状态取证已经把 blocker 收紧到“行绑定链断裂”：`receiveConfirm` 组件稳定出现 `total=300/page=1/pageSize=20`，但 `orderData/orderDetailData/orderHJData/orderDetailHJData/selectItem` 仍持续为空；`getDataList()` 只会再打一次 `SelDocConfirmList`，仍不填充本地行数组；`tableSelectClick/selectionChange` 也不会建立稳定选中态。更深一层的 ref probe 已确认 `reportTableItem_mainRef.RTM_searchConditions / RTM_toggleCheckboxRow` 都能调用，但不发新请求，也不填充 `orderData/selectItem`；其子 ref `RTM_reportTable` 已暴露 `tablePage`，而 `searchConditions/searchDataInfo/pageCondition/GetTotalData/allPageSelect` 这些子表方法也都能调用，但仍完全 no-op。新增头部链 probe 又确认：`reportTableItem_mainRef.RTM_GetViewGridHead` 会重发 `GetViewGridList`，`RTM_reportTable.getTableHeaders/getTableDataCount` 也能稳定构出 `tableColumn=6` 的表头结构，但 `allTableData/vxeTable.tableData` 仍始终为空，说明表头/视图元信息链是通的，真正缺的是行数据注入。新增父链 probe 进一步确认：`receiveConfirm.menuId` 与父链 `menuItemId.CheckDoc` 当前同值 `E003001001`，但 `detailData.currentItem` 仍为空，父链也只见壳层 tab/menu 集合，未见任何上游订单行缓存；而父链 refs 里的 `invoice01` 当前也只是回指同一个 `receiveConfirm` 实例，`navmenu` 未见任何附加数据载荷。最新子表 props/watcher probe 又确认：`RTM_reportTable` 虽然声明了 `tableData` 输入能力，但 `propsData` 当前只传 `databaseTableName/showFooter` 等视图参数；`vxeTable.database` 也只见本地库元信息，`allTableData/vxeTable.tableData/viewData/initHeaderData` 仍全空。进一步的数据库 probe 已坐实两层结果：IndexedDB 里 `FXDATABASE` 依然没有任何 object store，`receiveConfirm_E003001001_1` 并未落成本地表；而当前浏览器上下文里 `openDatabase` 也不可用，所以 `FXWebSQL` 更像元信息描述而不是可直接读取的本地表来源。最新 store probe 又确认 `receiveConfirm.$store.state` 当前只见 `cleardata=false`，`$root._data` 也只有 `yisEventHub`，并不存在可复用的订单缓存；同时新增的全局/注入上下文 probe 说明，`localStorage/sessionStorage/window` 层也没有额外订单缓存线索，壳层 `editableTabs` 也只保留 `FuncUrl/FuncName` 元信息，`yisEventHub._events` 为空，而 `vm` 注入字段虽然已经存在，但 `orderData/orderDetailData/orderHJData/selectItem/CheckList` 仍全是空数组，`detailData.pager.total` 仍是 `0`，`detailData` 本身也还只是壳对象。进一步的方法源码取证又确认，不仅 `receiveConfirm.getDataList/checkDetail/getDetailData/LogisticInfoClick` 自身都只暴露 `native code` 包装，连父链壳层方法也都只暴露 `native code` 包装，所以缺的更像更早的上游源数据注入，而不是子表本地翻页 | 主列表已 admit；二级动作链仍 blocked；需沿 `receiveConfirm.menuId / menuItemId.CheckDoc / detailData.currentItem / detailData.pager.total / editableTabs / yisEventHub / RTM_reportTable.props.tableData / FXDATABASE / receiveConfirm_E003001001_1` 这一断点继续回溯更早的上游数据注入点，确认为什么 `receiveConfirm / reportTableItem_mainRef / RTM_reportTable` 三层都有分页状态却始终没有行数据 | 单请求 |
| 门店盘点单 | `JyApi/EposDoc/SelDocManageList` | `POST` | `Authorization` | `bdate` `edate` `deptcode` `stat` `menuid` | 当前真实主列表接口已识别并完成 HTTP 回证；主列表已可按固定 `stat/date` 窗口准入 capture。页面 UI probe 与组件状态取证显示：DOM 仍是空表，但嵌套 `reportTable` 已能稳定拿到首行 `PdID=PD00000810`；进一步的组件方法取证显示，默认 `getDiffData()` 已能在本地填充完整 `orderDiffData=20` 和 `orderDiffHJData=2`，并已作为 `store_stocktaking_diff_records` 写入 capture research route，但按行 `getDiffData(row_1)` 目前会把 diff 状态清空，`row_2` 还拿不到稳定选中行，因此“统计损溢”更像本地派生的损溢总表，而不是已坐实的行级二级原始接口 | 主列表已 admit；统计损溢二级数据已进入 capture research 留痕；当前最高收益变成区分“默认损溢总表”与“按行损溢明细”的稳定性，并继续解释详情页为何仍不填充 `orderDetailData` | 单请求 |

---

## 3. 关键过滤条件分析

### 3.1 `JyApi` 与 `eposapi` 的差异

这一域混合了两类接口：

- `JyApi/*`
  - 使用 `Authorization: Bearer`
- `eposapi/*`
  - 使用 `token`

后续抓取器在这里必须按域区分认证头，不能统一硬塞一种写法。

### 3.2 `SearchType`

`每日流水单` 当前已确认：

- baseline 样本使用 `SearchType=1`
- `SearchType=blank/1/2/3/4/5` 在当前账号和默认时间窗下都返回同一份 `4045` 行集合

因此这条线现在可以先按“默认窗口单请求快照”写入 capture；后续如果页面或角色差异出现，再继续补更深的枚举语义。

### 3.3 多时间窗口月报

`门店销售月报` 不只是单区间查询：

- 当前区间：`BeginDate/EndDate`
- 同比区间：`YBeginDate/YEndDate`
- 环比区间：`MBeginDate/MEndDate`

因此它更适合作为经营结果快照，而不是基础事实源。

---

## 4. 维度重叠与失真风险

这一域和销售、库存都有重叠：

- `每日流水单` 和销售域存在金额核对重叠
- `出入库单据` 和库存域存在单据重叠
- `门店销售月报` 和销售域存在经营结果重叠

当前规则：

- `出入库单据` 继续归在库存事实候选链上
- `每日流水单`、`门店销售月报` 默认只做快照和对账

---

## 5. 当前建议

- 单据主源候选：`出入库单据`
- 流水快照候选：`每日流水单`
- 经营月报快照候选：`门店销售月报`

---

## 6. 后续待验证事项

1. `每日流水单` 后续是否存在角色差异或更大时间窗下的服务端数量限制
2. `门店销售月报.Type` 的完整枚举含义
3. `出入库单据.datetype/type/doctype` 的范围和是否互相独立
4. `退货明细` 仍需确认隐藏上下文或服务端边界；当前 `type` seed、`ReturnStockBaseInfo` 派生维度、页面真实点击后的查询请求，以及一层组件诊断都无法改变 post body，也都无法绕开 SQL 截断。更进一步地，`salesReturnDetailReport` 组件和 `RTM_searchConditions / RTM_getReportInfo` 方法已定位，但调用后仍不发新请求；最新方法体取证里不仅这两个方法只显示 `native code` 包装，`RTM_reportTable` 的 `searchConditions/searchDataInfo/pageCondition/getReportInfo/conditionStr` 这些关键方法同样只暴露 `native code` 包装，连 `salesReturnDetailReport` 根组件和上一层壳组件的查询/加载方法也都只暴露 `native code` 包装；同时 `RTM_reportTable` ref 已确认挂在 `FXDATABASE` 本地库链上，但浏览器实际打开后 `object_store_names` 为空，目标表 `salesReturnDetailReport` 并未落成本地表
5. `收货确认.page/pageSize/time/search` 为什么当前均不改变数据集，以及 `receiveConfirm.total=300`、空 DOM、空 `selectItem/orderData`、缺失的嵌套首行之间到底哪一层先失配；当前证据已经表明 `RTM_reportTable` 虽声明了 `tableData` 输入能力，但 `propsData` 未传任何数据集，`vxeTable.database` 指向的 `FXDATABASE` 在浏览器里没有任何 object store，`receiveConfirm_E003001001_1` 并未落成本地表；当前浏览器上下文里 `openDatabase` 也不可用，而 `receiveConfirm.$store.state` 只见 `cleardata=false`、`$root._data` 也未见订单缓存；同时不仅 `reportTableItem_mainRef` 与 `RTM_reportTable` 的关键方法源码都只暴露 `native code` 包装，连 `receiveConfirm.getDataList/checkDetail/getDetailData/LogisticInfoClick` 自身以及父链壳层方法也只暴露 `native code` 包装，因此下一步应继续追更早的上游数据注入点
6. `门店盘点单` 的 `统计损溢` 本地二级数据已按 `store_stocktaking_diff_records` 写入 capture research 路线，但当前只确认了默认 `getDiffData()` 能导出损溢总表；`getDiffData(row_1)` 仍会把 diff 状态清空，`row_2` 也还拿不到稳定选中行。下一步要先确认这条二级数据到底是“默认损溢总表”还是“可稳定按行展开的 secondary raw route”；同时继续解释为什么 `showDiffPage` 仍不打开、没有新请求，以及 `getDetailList(row)` 为什么仍不填充 `orderDetailData`
