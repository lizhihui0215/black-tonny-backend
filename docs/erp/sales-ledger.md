# 销售域接口台账

## 1. 当前目标

销售域优先解决三件事：

- 找到最适合作为明细源的接口
- 识别不同销售接口之间的重叠与口径差异
- 明确吊牌价、单价、金额、成本价字段的真实返回情况

---

## 2. 接口总表

| 页面/报表 | endpoint | method | 认证方式 | 主要过滤字段 | 当前判断 | 风险标签 | 抓取策略 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 零售明细统计 | `YisEposReport/SelDeptSaleList` | `POST` | `token` | `bdate` `edate` `depts` `spenum` `warecause` `page` `pagesize` | 更像销售明细结果接口，可作为销售域候选源 | 需要翻页 | 自动翻页 |
| 店铺零售清单 | `FXDIYReport/GetDIYReportData` | `POST` | `token` | `menuid` `gridid` `parameter.WareClause` `Depart` `BeginDate` `EndDate` `Operater` `Tiem` | DIY 明细表，强依赖菜单配置 | 需要扫枚举 | 暂不采纳 |
| 销售清单 | `FXDIYReport/GetDIYReportData` | `POST` | `token` | `menuid` `gridid` `parameter.BeginDate` `EndDate` `Depart` `Operater` `Tiem` `WareClause` | 当前最接近销售明细源，且字段最丰富 | 需要扫枚举 | 单请求 |
| 商品资料 | `YisEposWareList/SelWareList` | `POST` | `token` | `spenum` `warecause` `page` `pagesize` | 当前更像商品主数据页，已确认 `page` 为顺序翻页、`spenum` 支持精确收敛，主接口为 `SelWareList`；`warecause` 语义仍待确认 | 需要翻页 | 自动翻页 |
| 客户资料 | `YisEposDeptClientSet/SelDeptList` | `POST` | `token` | `deptname` `page` `pagesize` | 当前更像客户主数据页，已确认主接口为 `SelDeptList`；当前账号 baseline 为空数据集 | 需要翻页 | 自动翻页 |
| 商品销售情况 | `YisEposReport/SelSaleReportData` | `POST` | `token` | `bdate` `edate` `warecause` `spenum` | 更像商品维度聚合结果 | 只能当结果快照 | 结果快照 |
| 门店销售月报 | `JyApi/DeptMonthSalesReport/DeptMonthSalesReport` | `POST` | `Authorization` | `Type` `BeginDate` `EndDate` `YBeginDate` `YEndDate` `MBeginDate` `MEndDate` `PageIndex` `PageSize` | 月报结果接口，不宜直接当明细源 | 需要翻页 | 结果快照 |

---

## 3. 关键过滤条件分析

### 3.1 日期范围

销售域当前至少出现三套日期语义：

- `bdate/edate`
- `BeginDate/EndDate`
- 月报里的同比/环比窗口：
  - `YBeginDate/YEndDate`
  - `MBeginDate/MEndDate`

这意味着：

- 同一个“销售域接口”并不一定共享同一时间语义
- 月报类接口天然带多窗口比较，不应直接和单区间明细接口混算

### 3.2 组织范围

已知销售域里存在：

- `depts`
- `Depart`
- `Operater`
- `WareClause`

当前样本不能证明空值就是“全量”。

特别是 `FXDIYReport/GetDIYReportData` 这类接口，`Depart` 很可能受当前菜单和当前组织上下文共同影响。

### 3.3 DIY 报表隐藏条件

`销售清单` 和 `店铺零售清单` 都依赖：

- `menuid`
- `gridid`
- `parameter`

这类接口存在明显的“页面配置即查询语义”特征：

- 同一个 endpoint，不同 `menuid/gridid` 可能就是不同报表
- `parameter` 内某些字段可能不是独立业务条件，而是当前页面模板参数

因此这两类接口虽然字段丰富，但在未完全摸清菜单语义前，不能简单视为“可直接全量化”的统一明细源。

### 3.4 同一菜单下的多 grid 粒度

当前已经确认 `menuid=E004001008` 下面至少存在两套销售查询粒度：

- `gridid=E004001008_2`
  - 通过 `FXDIYReport/GetDIYReportData`
  - 当前更接近“按明细”或“按行”粒度
- `gridid=E004001008_1`
  - 通过 `JyApi/Grid/GetViewGridList` 可确认它是同一菜单下的另一套 grid 定义
  - 当前与 `YisEposReport/SelSaleReport` 这条“按单据”查询更相关

这不是一个小差异，而是销售域建模时必须优先收口的边界：

- `按明细`
  - 更适合承接商品、款色尺码、件数、折扣、单行金额等分析
- `按单据`
  - 更适合承接订单数、单据金额、客单价、支付单汇总等分析

因此后续必须把它们当成“两条不同粒度的数据源”处理，而不是当成同一张表的别名。

### 3.5 当前已确认的粒度结论

这条线现在已经不只是推测，而是有真实返回支撑：

- `gridid=E004001008_1`
  - `GetViewGridList` 返回 `31` 个字段
  - 核心列包括：
    - `SaleDate`
    - `SaleNum`
    - `OperMan`
    - `TotalSaleAmount`
    - `TotalSaleRetailMoney`
    - `TotalSaleMoney`
    - `ReceiveMoney`
  - 这些字段天然更像“单据头/销售单汇总”粒度
- `SelSaleReport`
  - 当前首屏返回 `3717` 行
  - 真实字段包括：
    - `SaleNum`
    - `SaleDate`
    - `OperMan`
    - `TotalSaleAmount`
    - `TotalSaleMoney`
    - `ReceiveMoney`
    - `Cash`
    - `CreditCard`
    - `OrderMoney`
    - `StockMoney`
  - 这条路线已经可以明确视为“单据头候选源”
- `gridid=E004001008_2`
  - `GetViewGridList` 返回 `53` 个字段
  - 核心列包括：
    - `零售单号`
    - `明细流水`
    - `款号`
    - `品名`
    - `吊牌价`
    - `单价`
    - `颜色`
    - `尺码`
    - `数量`
    - `金额`
    - `吊牌金额`
  - 这些字段天然更像“明细行/商品行”粒度
- `销售清单(gridid=_2)`
  - 当前继续作为“明细行候选源”研究

当前最重要的结论是：

- `_1 + SelSaleReport` 可以视为订单头候选路线
- `_2 + 销售清单` 可以视为订单行候选路线
- 两者共同候选关联键优先看：
  - `SaleNum`
  - `零售单号`
  - `销售日期`
  - `导购员`

其中最值得继续验证的是 `SaleNum/零售单号` 是否能稳定做头行关联。

当前这条判断已经有结构化分析脚本支撑：

- 脚本：`scripts/analyze_yeusoft_sales_menu_grains.py`
- 最新样本输出：`tmp/capture-samples/analysis/sales-menu-grain-20260321-230552.json`

在这份最新输出里：

- `document_grid_kind = document_header_schema`
- `document_data_kind = document_header_candidate`
- `detail_grid_kind = line_detail_schema`
- `detail_data_kind = line_detail_candidate`
- `candidate_join_keys = [sale_no, sale_date, vip_card_no]`

这进一步说明：当前唯一应继续作为主关联键推进的是 `sale_no`；`sale_date` 与 `vip_card_no` 更适合做上下文或辅助校验。

---

## 4. 销售主线证据闭环

当前已经新增销售主线证据闭环脚本：

- 脚本：`scripts/analyze_yeusoft_sales_evidence_chain.py`
- 最新输出：`tmp/capture-samples/analysis/sales-evidence-chain-20260322-171553.json`

这条脚本会把：

- 页面研究结论
- 纯 HTTP 回证
- 头/行候选关联统计
- `零售明细统计` 对账摘要

收成一份结构化证据。

### 4.1 当前已确认结论

- `SelSaleReport`
  - 继续作为订单头候选源
  - 当前真实返回 `3717` 行
- `GetDIYReportData(menuid=E004001008, gridid=_2)`
  - 继续作为明细行候选源
  - 当前真实返回 `9852` 行
- `SelDeptSaleList`
  - 当前继续只作为研究/对账源
  - 不直接接入 `sales_orders / sales_order_items`

### 4.2 头行关联键最新结论

当前脚本已对以下候选键做了命中率统计：

- `sale_no`
- `sale_date`
- `vip_card_no`

当前结果：

- `sale_no`
  - `document_overlap_rate = 1.0`
  - `detail_overlap_rate ≈ 0.9276`
  - 关系为 `one_to_many`
  - 当前可视为最稳定的头行关联键
- `vip_card_no`
  - 当前也表现为稳定关联键
  - 但它更适合辅助校验，不适合作为头行主键
- `sale_date`
  - 当前不再作为主关联键推进
  - 只保留为上下文字段

当前 field ownership 也已明确：

- 订单头专有字段：
  - `received_amount`
  - `sales_qty`
  - `cash`
  - `creditcard`
  - `stockmoney`
  - 等支付/汇总类字段
- 明细行专有字段：
  - `detail_serial`
  - `style_code`
  - `product_name`
  - `quantity`
  - `tag_price`
  - `unit_price`
  - `color`
  - `size`
  - `成本价`
  - 等商品与行级属性字段

### 4.3 参数语义最新结论

对 `销售清单(_2)` 的单变量纯 HTTP 回证结果：

- `parameter.Tiem`
  - 当前为 `same_dataset`
  - 说明 `0 / 1 / 2` 在当前账号下没有切出新的数据集
- `parameter.BeginDate`
  - 当前为 `scope_or_date_boundary`
  - 压缩到单日后结果显著收窄
- `parameter.EndDate`
  - 当前为 `scope_or_date_boundary`
  - 压缩到单日后结果显著收窄
- `parameter.Depart`
  - 当前为 `scope_or_date_boundary`
  - 说明它不能被当成无意义空参数，后续正式抓取必须明确门店范围

对 `零售明细统计` 的回证结果：

- `page`
  - 当前为 `pagination_page_switch`
  - `page=0,pagesize=20` 与 `page=1,pagesize=20` 返回不同数据子集
- `edate`
  - 当对齐到销售主线相同的结束日期窗口时，当前为 `same_dataset`
  - 说明 `20260401` 与默认样本里的 `20260430` 在当前账号下没有切出新的数据集
  - 但如果把 `edate` 直接压到与 `bdate` 同一天，会退化成单行宽表结果
  - 这条现在可以视为“正常窗口下可用，单日极端窗口有 edge case”

### 4.4 对账粒度收口

`零售明细统计` 与 `销售清单` 当前已经能确认不是同一层粒度：

- `销售清单(_2)` 的 `9852` 行是明细行
- `零售明细统计` 的 `1353` 行是按 `款号 / 颜色 / 吊牌价` 收口后的宽表结果

把 `销售清单(_2)` 按同一组键聚合后，当前已经能得到：

- 聚合后行数：`1353`
- 与 `零售明细统计` 的交集键数：`1353`
- `quantity_total`：`一致`
- `amount_total`：`可接受差异`

所以：

- `line_count` 已不再是待解释 blocker
- `sales_list_order_count` 也不应该再和 `零售明细统计` 直接对账
  - 因为这条宽表当前不提供稳定单据号
  - 它只能继续承担研究 / 对账源角色，不能承担订单数来源角色

### 4.5 正常销售与逆向单据分流

最新证据闭环已经把销售明细按 `sale_no` 拆成三层：

- `sales_documents_head`
  - 只保留订单头里存在的 `sale_no`
- `sales_document_lines`
  - 只保留明细里且订单头也存在的 `sale_no`
- `sales_reverse_document_lines`
  - 只保留明细里存在、但订单头里不存在的 `sale_no`

当前这条逆向路线的结构化统计是：

- `detail_only_sale_no_count = 290`
- `detail_only_row_count = 771`
- `negative_only_sale_no_count = 69`
- `mixed_sign_sale_no_count = 221`

当前结论：

- 正常销售主链已经具备首批 capture 准入条件
- 逆向单据不再混入正常销售主链
- `sales_reverse_document_lines` 先只保留为 capture 研究留痕路线，不进入 `serving` 或 dashboard 主链

### 4.6 当前 issue flags

当前自动 `issue_flags` 已清零，销售主线的旧 blocker 已经移除：

- `line_count`
- `sales_list_order_count`
- `SelDeptSaleList.edate`

当前真正保留的边界是：

- `sale_no` 是唯一主关联键
- `sale_date`、`vip_card_no` 只做上下文或辅助校验
- `SelDeptSaleList` 继续只做研究 / 对账源
- `sales_reverse_document_lines` 继续只做研究留痕，不进入主链

---

## 5. 维度重叠与失真风险

### 4.1 当前重叠关系

销售域当前至少有两组重叠：

- 明细或准明细候选：
  - `零售明细统计`
  - `店铺零售清单`
  - `销售清单`
- 聚合或快照候选：
  - `商品销售情况`
  - `门店销售月报`

### 4.2 当前规则

- `销售清单` 暂时视为销售域字段最完整的候选主源接口
- `零售明细统计` 适合作为对账和备用候选
- `店铺零售清单` 暂时保留为待研究接口，不直接进入 capture 主链
- `商品销售情况`、`门店销售月报` 只当结果快照，不和明细源直接混算
- `销售清单-按明细` 与 `销售清单-按单据` 必须拆开评估，禁止直接拼接或双计

### 4.3 为什么这条分析有意义

这条线值得继续做，不是因为“多发现了一个接口”，而是因为它会直接影响后面数据是否有意义：

- 如果我们把“按单据”和“按明细”混成同一层事实表：
  - 订单数会被重复放大
  - 单据金额和行金额可能被双计
  - 客单价会失真
  - 连带率和销售件数也可能因为粒度不一致而被错误解释
- 如果把它们拆清：
  - `按单据` 可以作为订单头候选源
  - `按明细` 可以作为订单行候选源
  - 两者可以通过 `DocNo/单据号` 一类字段做头行关联验证

所以这条分析不是“可选优化”，而是销售域是否能形成可靠主链的前置工作。

---

## 6. 成本与金额字段现状

### 5.1 `销售清单`

当前真实样本已确认：

- 存在 `吊牌价`
- 存在 `吊牌金额`
- 存在 `成本价` 列头

但进一步检查同一份响应的 `Data`：

- 总行数：`9839`
- `成本价` 非空行数：`0`

当前结论：

- 这不是“字段没找到”
- 而是“列头存在但值为空”
- 更像当前账号权限、菜单配置或字段裁剪问题

### 5.2 `零售明细统计`

当前样本尚未确认存在稳定的成本字段。

### 5.3 `商品销售情况`

当前更偏结果快照接口，后续需要单独核实是否包含毛利/成本相关字段。

---

## 7. 当前建议

- 短期主源候选：
  - 订单头：`SelSaleReport`
  - 明细行：`销售清单(gridid=_2)`
- 对账候选：`零售明细统计`
- 研究留痕候选：`sales_reverse_document_lines`
- 快照候选：`商品销售情况`、`门店销售月报`
- 暂缓直接采纳：`店铺零售清单`

---

## 8. 当前探索策略

当前自动探索只先覆盖：

### 7.1 `销售清单`

- 不先做分页探测
- 先探测 `parameter.Tiem`
- 默认候选值按当前样本和有限补充值展开
- `parameter.Depart` 只当上下文字段记录，不自动 sweep

当前目标：

- 判断 `Tiem` 是切视图还是切数据子集
- 判断不同 `Tiem` 下，行数、字段、成本列状态是否变化

### 7.2 页面研究链如何服务销售域

除了纯 HTTP 样本分析，现在销售域还会走一条浏览器研究链：

- 打开真实页面
- 记录基线请求
- 单独切换页面动作
- 记录参数变化和响应签名变化

这条研究链的目的不是替代正式抓取，而是确认：

- `销售清单` 页面下哪些动作会切到 `_1 / _2`
- `按单据 / 按明细` 是否真的对应不同接口路线
- 页面上隐藏参数是否会改变 `menuid/gridid/parameter`
- 哪些结论足够稳定，可以回写到纯 HTTP 主链

对应运行说明见：

- `docs/erp/page-research-runbook.md`
- 补齐 `menuid=E004001008` 下 `gridid=_1` 和 `gridid=_2` 的列定义差异
- 判断 `GetDIYReportData(gridid=_2)` 的明细粒度，和 `SelSaleReport + gridid=_1` 的单据粒度是否可建立头行关系

当前已经有一条可复跑的专项脚本：

```bash
python3 scripts/analyze_yeusoft_sales_menu_grains.py
```

它会直接输出：

- `_1` grid 列定义
- `_2` grid 列定义
- `SelSaleReport` 单据头字段
- `销售清单(gridid=_2)` 明细字段
- 以及候选关联键结论

### 7.3 `零售明细统计`

- 先探测 `page/pagesize`
- 优先验证 `pagesize=0` 是否真等于全量
- 再用有限页数探测额外页是否存在

当前目标：

- 判断该接口是否需要正式自动翻页
- 判断它和 `销售清单` 是否存在可复用的对账关系

### 7.4 第二轮单变量深挖结论

- `销售清单`
  - 第二轮页面研究已直接在同一份 manifest 里跑出两条真实数据路线：
    - `SelSaleReport`：`3717` 行，稳定落在单据头路线
    - `GetDIYReportData(gridid=_2)`：`9852` 行，稳定落在明细行路线
  - 当前 `grain_route` 已明确是 `multi_grain_route`
  - 当前候选关联键已经收敛为：
    - `sale_no`
    - `sale_date`
    - `vip_card_no`
  - `parameter.Tiem=0/1/2` 在当前账号与时间范围下：
    - 行数一致
    - 列结构一致
    - `row_set_signature` 一致
  - 当前可判定为 `same_dataset`
  - 也就是说，现阶段没有证据支持把 `Tiem` 当成必须 sweep 的数据范围参数
  - `parameter.BeginDate`、`parameter.EndDate` 在被压成单日时都返回 `0` 行
    - 这说明日期参数当然会影响结果
    - 但当前还不足以直接定义它们的完整边界语义
  - `parameter.Depart` 置空时没有稳定拿到可读响应，仍保留为后续范围审计项
- `零售明细统计`
  - 第二轮页面研究确认它的主数据接口仍是 `SelDeptSaleList`
  - `page=0,pagesize=20` 返回 `1353` 行
  - `page=1,pagesize=20` 返回 `20` 行，且 `row_set_signature` 明显变化
  - 这说明它至少具备“页码会切数据子集”的语义
  - 但当前页面级单变量证据还不足以把 `pagesize/page` 各自单独判成最终语义，所以仍保留 `needs_followup`
  - 结合前一轮 HTTP 对账结果，当前更稳妥的定位仍然是：
    - 销售域研究/对账源
    - 暂不直接接入 dashboard 顶部 8 张卡主链

### 7.5 第一轮真实探索结论

- `销售清单`
  - 当前账号下，`parameter.Tiem=0/1/2` 没有带来可观察到的返回签名差异
  - 在当前样本范围内，暂不需要因为 `Tiem` 单独做枚举 sweep
  - `成本价` 列仍然存在且值全空，继续作为权限/字段可见性审计项
  - `menuid=E004001008` 当前已确认至少存在两个 grid 变体：
    - `gridid=_2`：按明细
    - `gridid=_1`：按单据
  - 当前这两条路线都值得保留，但必须拆成不同粒度研究，不能直接视为重复接口
- `零售明细统计`
  - `page=0,pagesize=0` 与 `page=0,pagesize=20` 当前都返回 1353 行
  - `page=1,pagesize=20` 返回 20 行，说明分页语义不能直接忽略
  - 后续继续保留为正式分页对账候选，不提升为销售事实主源

### 7.6 正式分页抓取策略

- 正式抓取统一使用 `page=0,pagesize=20` 起步，不再把 `pagesize=0` 当主链参数
- 若 `page=0,pagesize=20` 已直接返回超过 `pagesize` 的全量行数，则判定为“首屏即全量”并立即停止
- 只有首屏未直接回全量时，才继续按 `page=1,2,3...` 顺序抓取
- 当返回行数为 `0`，或当前页返回签名与上一页完全重复时停止
- capture 层使用独立 canonical endpoint：`sales_retail_detail_stats`
- 当前它仍是销售域对账源，不直接进入 dashboard 顶部 8 张卡主链

### 7.7 首屏 page-size 研究结论

- `销售清单`
  - 当前请求体没有显式 `page/pagesize` 字段
  - 不适用首屏大 `pagesize` 探测
  - 当前仍按单请求 fresh 抓取研究
- `零售明细统计`
  - 当前已确认 `page=0,pagesize=20` 首屏直接返回 `1353` 行
  - `20 / 100 / 1000 / 10000 / 0` 的首屏返回签名一致，都是同一批 `1353` 行
  - 这已经强烈说明首屏存在“超页即全量”的特殊行为
  - 当前推荐第一页大小继续保持 `20`
  - 大页参数目前只会被标记为 `large_page_ignored`，不会进入正式抓取默认值
  - 后续的大页尺寸探测只能作为更强证据补充，不能反向覆盖这条已确认事实
  - 如首屏探测命中 `10000` 行阈值，才会追加更大的 edge size 试探

---

## 8. 后续待验证事项

1. `Depart` 空值、指定门店、当前门店三种情况下是否返回相同范围
2. `sales_reverse_document_lines` 里的 `290` 个 `sale_no` 是否能进一步拆成退货 / 换货 / 逆向流水
3. `商品销售情况` 是否存在可用于毛利或成本的字段
4. 不同角色账号下 `销售清单.成本价` 是否仍然全为空
5. `SelSaleReport` 是否可作为订单头候选源，供 dashboard 的订单数/客单价口径使用
6. `sale_no` 驱动的头 / 行 / 逆向三路分流，在连续批次下是否保持稳定
