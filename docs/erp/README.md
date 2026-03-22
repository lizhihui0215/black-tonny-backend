# ERP 接口研究总览

> 当前统一状态面板见 [ERP API 成熟度总览](./api-maturity-board.md)，推进路线见 [ERP Capture 全量导入路线图](./capture-ingestion-roadmap.md)。以后新开窗口，先看状态板里“全域风险地图是否已完成”，再看路线图，再往下看分域台账和 analysis 证据文件。

补充说明：

- 这里的“全域”当前默认指“当前账号可见全域”，不是系统全部角色、全部租户的绝对全量。
- 这层边界现在由菜单覆盖审计来证明，不再只靠已知样本和 ledger。

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

- [ERP API 成熟度总览](./api-maturity-board.md)
- [ERP Capture 全量导入路线图](./capture-ingestion-roadmap.md)
- [销售域台账](./sales-ledger.md)
- [库存域台账](./inventory-ledger.md)
- [会员域台账](./member-ledger.md)
- [储值域台账](./stored-value-ledger.md)
- [流水与单据域台账](./payment-and-doc-ledger.md)
- [成本字段可见性审计](./cost-visibility-audit.md)
- [页面研究运行说明](./page-research-runbook.md)
- 最新菜单覆盖审计产物：`tmp/capture-samples/analysis/menu-coverage-audit-*.json`

---

## 6. 推荐阅读顺序

1. 先看 `api-maturity-board.md`，确认做到哪里、是否可信、还能不能进主链
2. 再看 `capture-ingestion-roadmap.md`，确认下一步按什么顺序推进到 `capture`
3. 再看这份总览，理解统一边界、术语和研究方法
4. 再看分域台账，理解接口、过滤条件和抓取策略
5. 最后看成本字段可见性专题，确认当前成本相关能力边界

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

当前还新增了一条探索模式，直接复用主抓取脚本：

```bash
python3 scripts/fetch_yeusoft_report_payloads.py --mode explore --explore-target sales_inventory
```

这条模式当前只先覆盖销售域和库存域的第一批高价值接口：

- `销售清单`
- `零售明细统计`
- `库存明细统计`
- `出入库单据`

当前还新增了一条销售主线证据闭环分析脚本：

```bash
.venv/bin/python scripts/analyze_yeusoft_sales_evidence_chain.py
```

这条脚本会把三条销售路线收成一份结构化证据：

- `SelSaleReport`：订单头候选源
- `GetDIYReportData(menuid=E004001008, gridid=_2)`：明细行候选源
- `SelDeptSaleList`：研究/对账源

- 默认输出到：
  - `tmp/capture-samples/analysis/sales-evidence-chain-*.json`

- 并自动产出：
  - 头/行候选关联统计
  - `parameter.Tiem / BeginDate / EndDate / Depart` 的 HTTP 回证语义
  - `SelDeptSaleList` 的分页差异与对账摘要
  - `issue_flags`，用于持续标记尚未收口的问题

当前还新增了一条菜单覆盖审计脚本：

```bash
.venv/bin/python scripts/run_yeusoft_menu_coverage_audit.py \
  --headless \
  --skip-screenshots
```

这条脚本会：

- 导出当前账号完整菜单树
- 审计每个可点击页面是否能成功打开
- 标记 `covered / visible_but_untracked / visible_but_failed / container_only`
- 把 unknown page 作为占位 route 补回状态板
- 默认输出到：
  - `tmp/capture-samples/analysis/menu-coverage-audit-*.json`

当前也支持直接补齐菜单覆盖审计里发现的 unknown page 基线：

```bash
.venv/bin/python scripts/run_yeusoft_page_research.py \
  --headless \
  --skip-screenshots \
  --unknown-pages-only
```

这条命令会把最新 `menu-coverage-audit-*.json` 里的 `visible_but_untracked` 页面并入研究 runner。跑完后再重跑菜单覆盖审计和状态板，就可以把 unknown 占位项替换成真实路线。

页面研究链的第二轮单变量深挖入口是：

```bash
.venv/bin/python scripts/run_yeusoft_page_research.py \
  --headless \
  --skip-screenshots \
  --probe-target sales_inventory
```

当前这条研究链已经能直接产出：

- `baseline_request_signature`
- `single_variable_probe_results`
- `parameter_semantics`
- `grain_route`
- `candidate_join_keys`

页面研究第一轮目前已经改成“真实父页面 + 变体别名”模型：

- 样本/截图中的分析变体页会保留研究标题
- 实际打开线上真实菜单页
- 再在 manifest 中记录变体标签和真实菜单落点

这样可以提高基线覆盖率，同时避免把截图里的变体名误当成线上真实菜单项。

---

## 8. 页面研究链

除了纯 HTTP 抓取和样本分析，现在还补了一条浏览器研究链，用来做：

- 菜单到接口映射
- 页面动作到参数变化映射
- 多 grid / 多粒度页面判定
- 页面证据链沉淀

它只用于研究，不进入正式定时抓取主链。

运行入口：

```bash
.venv/bin/python scripts/run_yeusoft_page_research.py
```

后处理入口：

```bash
.venv/bin/python scripts/postprocess_yeusoft_page_research.py
```

详细说明见：

- [页面研究运行说明](./page-research-runbook.md)

默认行为是：

- 先探测
- 不默认写 `capture`
- 结果落到 `tmp/capture-samples/exploration/`

如果确实需要把探索请求一并留痕到 `capture`，再显式加：

```bash
--persist-detection
```

如果要专项确认销售菜单在“按单据 / 按明细”两种粒度下的字段差异，可以直接运行：

```bash
python3 scripts/analyze_yeusoft_sales_menu_grains.py
```

默认输出到：

- `tmp/capture-samples/analysis/sales-menu-grain-*.json`

它会同批抓取：

- `menuid=E004001008, gridid=_1` 的 grid 定义
- `menuid=E004001008, gridid=_2` 的 grid 定义
- `SelSaleReport` 的按单据数据
- 当前 `销售清单(gridid=_2)` 的按明细数据

并自动给出：

- 哪条更像单据头候选源
- 哪条更像明细行候选源
- 哪些字段可作为头行关联键候选

---

## 8. 大页尺寸探测

在不改变正式抓取主链的前提下，当前探索模式已经支持“首屏大 `pagesize` 探测”。

默认候选值固定为：

- `20`
- `100`
- `1000`
- `10000`
- `0`

默认只比较首屏，不和完整翻页逻辑混跑，所以这层结论只用于研究：

- 大 `pagesize` 是否真的增加返回数据
- `0` 是否等于全量
- 某接口是否存在“参数被接受但结果没变化”

推荐命令：

```bash
python3 scripts/fetch_yeusoft_report_payloads.py --mode explore --explore-target sales_inventory
```

如果要做更激进的边缘试探，可以显式追加更大的 size：

```bash
python3 scripts/fetch_yeusoft_report_payloads.py \
  --mode explore \
  --explore-target sales_inventory \
  --edge-page-size 50000 \
  --edge-page-size 100000
```

注意：

- 这些更大的 size 只作为研究参数
- 不会一上来就全部执行
- 只有当默认首屏探测发现 `10000` 或 `0` 已经命中 `10000` 行阈值时，才会继续触发这些 edge size
- 不会自动回写正式抓取器
- 只有当结果稳定后，才会单独评估是否把更优的第一页大小引入主链
