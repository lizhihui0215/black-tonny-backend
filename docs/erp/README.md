# ERP 接口研究总览

## 1. 这套文档的作用

这套文档用于长期记录 Yeusoft ERP 在当前合法账号范围内的：

- 接口发现情况
- 过滤条件与分页语义
- 维度重叠与数据失真风险
- 成本字段、吊牌价字段、金额字段的可见性差异
- 哪些接口值得进入 `capture` 主链
- 哪些接口只能作为结果快照或校对接口

这不是“破解文档”。

当前研究边界固定为：

- 只研究合法账号、合法角色下的接口能力
- 只做权限边界审计，不做绕权、未授权访问或破解
- 运行时主链路优先采用纯 HTTP 抓取
- 浏览器只保留为研究辅助工具，不作为正式依赖

---

## 2. 当前已经确认的认证链

当前已经确认可稳定运行的纯 HTTP 认证链如下：

1. `CompanyUserPassWord`
2. `Login`
3. `RefreshToken`
4. ERP 报表/查询接口

关键点：

- `Login` 响应头会返回 `access-token`
- `Login` 响应头还会返回 `x-access-token`
- `RefreshToken` 需要同时带：
  - `Authorization: Bearer <access-token>`
  - `X-Authorization: Bearer <x-access-token>`
- ERP 侧大部分 `eposapi` / `FxErpApi` 接口使用 `token` 请求头
- `JyApi` 侧接口使用 `Authorization: Bearer <token>`

当前主结论：

- 正式抓取不需要浏览器常驻
- 浏览器只在逆向研究或字段确认时作为辅助

---

## 3. 统一术语

### 3.1 接口分类

- `源接口`
  - 更接近明细或准明细数据源
  - 适合进入 `capture` 主链，后续可投影到 `serving`
- `结果快照接口`
  - 更像页面统计结果、分析视图或聚合结果
  - 适合做快照、对账或口径校验
  - 默认不直接当成事实明细源

### 3.2 风险标签

- `大概率全量`
  - 当前样本下没有明显分页或隐含枚举风险
- `需要翻页`
  - 样本已出现 `page/pagesize` 或 `PageIndex/PageSize`
- `需要扫枚举`
  - 样本已出现 `rtype/type/SearchType/datetype/stockflag/doctype` 等视图枚举
- `只能当结果快照`
  - 接口更像聚合结果，不宜直接当作明细源

### 3.3 抓取策略标签

- `单请求`
- `自动翻页`
- `枚举 sweep`
- `结果快照`
- `暂不采纳`

---

## 4. 当前核心结论

### 4.1 过滤条件会直接影响是否漏数

当前已知接口样本里，常见过滤条件主要有：

- 日期范围：`bdate/edate`、`BeginDate/EndDate`、`salebdate/saleedate`
- 组织范围：`Depart`、`depts`、`warecause`、`Operater`
- 搜索条件：`Search`、`SearchType`、`condition`、`searchval`
- 视图枚举：`rtype`、`type`、`datetype`、`stockflag`、`doctype`
- 分页字段：`page/pagesize`、`PageIndex/PageSize`
- DIY 报表上下文：`menuid`、`gridid`、`parameter`

当前不能直接把“空字符串”理解成“全量”：

- 它很可能只是“当前账号上下文范围”
- 也可能仍然受当前门店、角色、菜单配置影响

### 4.2 同一业务域可能有多个接口返回相近内容

例如销售域已经确认存在以下重叠关系：

- `销售清单`
- `店铺零售清单`
- `零售明细统计`
- `商品销售情况`
- `门店销售月报`

这些接口都和销售表现有关，但不等于可以直接混算：

- 有的更像明细源
- 有的更像按维度聚合后的视图
- 有的更像结果快照

后续文档里必须明确“主源接口”和“仅校验/快照接口”，避免重复入库导致数据失真。

### 4.3 成本字段不是“没找到”，而是“当前返回受限”

当前已经确认两条关键事实：

- `销售清单` 的真实响应里存在 `成本价` 列头
- 但当前账号样本下，`Data` 中 9839 行该列值全部为空

同时：

- `库存明细统计` 的样本里稳定返回 `RetailPrice`
- 当前未见对应 `CostPrice` 字段

这说明当前更像：

- 字段受角色/权限/菜单配置裁剪
- 或者后端保留列头但不返回具体值

而不是：

- 我们还没找到正确字段名

### 4.4 当前文档目标

后续所有接口研究，都要回答以下问题：

1. 这个接口是不是源接口
2. 它会不会漏页
3. 它有没有枚举型视图
4. 它的空组织字段是不是只代表当前账号范围
5. 它是否和别的接口返回相同业务内容
6. 它有没有成本/金额/吊牌价/零售价字段
7. 这些字段是缺失、为空，还是受角色差异影响

---

## 5. 文档目录

- [销售域台账](./sales-ledger.md)
- [库存域台账](./inventory-ledger.md)
- [会员域台账](./member-ledger.md)
- [储值域台账](./stored-value-ledger.md)
- [流水与单据域台账](./payment-and-doc-ledger.md)
- [成本字段可见性审计](./cost-visibility-audit.md)

---

## 6. 推荐阅读顺序

1. 先看这份总览
2. 再看分域台账，理解接口、过滤条件和抓取策略
3. 最后看成本字段可见性专题，确认当前成本相关能力边界

如果是为了继续实现抓取链，建议再结合这些 backend 文档一起看：

- `docs/two-database-architecture.md`
- `docs/dashboard/08-summary-capture-mapping.md`

---

## 7. 研究辅助工具

当前已经提供一个样本分析脚本，用来自动扫描：

- 请求里的日期、组织、搜索、枚举、分页和 DIY 上下文字段
- 样本响应里的行数、列数
- 成本字段是否存在
- 吊牌价 / 零售价字段是否存在
- 当前接口建议的抓取策略和风险标签

运行方式：

```bash
python3 scripts/analyze_yeusoft_report_samples.py
```

默认输出到：

- `tmp/capture-samples/analysis/report-matrix-*.json`

这份输出适合作为后续：

- 过滤条件探索
- 分页策略补齐
- 角色差异审计
- capture 主链接口优先级排序

的基础输入。
