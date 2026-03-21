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

---

## 4. 维度重叠与失真风险

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

---

## 5. 成本与金额字段现状

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

## 6. 当前建议

- 短期主源候选：`销售清单`
- 对账候选：`零售明细统计`
- 快照候选：`商品销售情况`、`门店销售月报`
- 暂缓直接采纳：`店铺零售清单`

---

## 7. 当前探索策略

当前自动探索只先覆盖：

### 7.1 `销售清单`

- 不先做分页探测
- 先探测 `parameter.Tiem`
- 默认候选值按当前样本和有限补充值展开
- `parameter.Depart` 只当上下文字段记录，不自动 sweep

当前目标：

- 判断 `Tiem` 是切视图还是切数据子集
- 判断不同 `Tiem` 下，行数、字段、成本列状态是否变化

### 7.2 `零售明细统计`

- 先探测 `page/pagesize`
- 优先验证 `pagesize=0` 是否真等于全量
- 再用有限页数探测额外页是否存在

当前目标：

- 判断该接口是否需要正式自动翻页
- 判断它和 `销售清单` 是否存在可复用的对账关系

### 7.3 第一轮真实探索结论

- `销售清单`
  - 当前账号下，`parameter.Tiem=0/1/2` 没有带来可观察到的返回签名差异
  - 在当前样本范围内，暂不需要因为 `Tiem` 单独做枚举 sweep
  - `成本价` 列仍然存在且值全空，继续作为权限/字段可见性审计项
- `零售明细统计`
  - `page=0,pagesize=0` 与 `page=0,pagesize=20` 当前都返回 1352 行
- `page=1,pagesize=20` 返回 20 行，说明分页语义不能直接忽略
- 后续应优先把它升级为正式分页抓取候选

### 7.4 正式分页抓取策略

- 正式抓取统一使用 `page=0,pagesize=20` 起步，不再把 `pagesize=0` 当主链参数
- 若 `page=0,pagesize=20` 已直接返回超过 `pagesize` 的全量行数，则判定为“首屏即全量”并立即停止
- 只有首屏未直接回全量时，才继续按 `page=1,2,3...` 顺序抓取
- 当返回行数为 `0`，或当前页返回签名与上一页完全重复时停止
- capture 层使用独立 canonical endpoint：`sales_retail_detail_stats`
- 当前它仍是销售域对账源，不直接进入 dashboard 顶部 8 张卡主链

---

## 8. 后续待验证事项

1. `销售清单` 的 `parameter.Tiem` 是否是视图切换枚举
2. `Depart` 空值、指定门店、当前门店三种情况下是否返回相同范围
3. `零售明细统计` 的 `page=0/pagesize=0` 是否真等于全量
4. `商品销售情况` 是否存在可用于毛利或成本的字段
5. 不同角色账号下 `销售清单.成本价` 是否仍然全为空
