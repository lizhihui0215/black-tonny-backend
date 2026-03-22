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
| 每日流水单 | `JyApi/ReconciliationAnalysis/SelectRetailDocPaymentSlip` | `POST` | `Authorization` | `MenuID` `SearchType` `Search` `LastDate` `BeginDate` `EndDate` | 支付流水结果接口，高价值但需继续摸清查询语义 | 需要扫枚举 | 结果快照 |
| 出入库单据 | `YisEposReport/SelOutInStockReport` | `POST` | `token` | `bdate` `edate` `datetype` `type` `doctype` `spenum` `warecause` `page` `pagesize` | 单据明细候选，和库存域强相关 | 需要扫枚举 | 自动翻页 |
| 门店销售月报 | `JyApi/DeptMonthSalesReport/DeptMonthSalesReport` | `POST` | `Authorization` | `Type` `BeginDate` `EndDate` `YBeginDate` `YEndDate` `MBeginDate` `MEndDate` `PageIndex` `PageSize` | 经营月报结果视图 | 需要翻页 | 结果快照 |
| 退货明细 | `GetViewGridList` | `页面基线` | `浏览器研究` | `待补页面查询条件` | 当前更像退货业务明细页，已完成页面基线，但稳定主接口仍待识别 | 主接口待识别 | 待识别 |
| 收货确认 | `GetViewGridList` | `页面基线` | `浏览器研究` | `默认加载` | 当前更像收货确认单据页，已完成页面基线，但稳定主接口仍待识别 | 主接口待识别 | 待识别 |
| 门店盘点单 | `GetViewGridList` | `页面基线` | `浏览器研究` | `默认加载` | 当前更像盘点单据页，已完成页面基线，但稳定主接口仍待识别 | 主接口待识别 | 待识别 |

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

`每日流水单` 当前样本里有：

- `SearchType=1`

这类字段大概率是查询模式枚举，而不是普通过滤值。

如果不探索完整枚举集合，很容易只抓到一种流水视图。

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

1. `每日流水单.SearchType` 的完整枚举
2. `每日流水单` 是否存在分页或服务端数量限制
3. `门店销售月报.Type` 的完整枚举含义
4. `出入库单据.datetype/type/doctype` 的范围和是否互相独立
