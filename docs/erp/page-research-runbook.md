# Yeusoft 页面研究运行说明

## 1. 目标

这套页面研究链只做一件事：

- 用真实页面操作找出菜单、接口、参数变化、粒度关系和漏数风险

它不是正式抓取主链。

正式抓取仍然回落到纯 HTTP。

## 2. 运行边界

- 只研究当前合法账号
- 只读，不碰写操作
- 浏览器只做研究，不做正式定时抓取
- 原始浏览器证据默认只落本地，不纳入正式仓库

## 3. 一次性准备

安装 research 依赖：

```bash
.venv/bin/pip install -e '.[research]'
.venv/bin/python -m playwright install chromium
```

首次手工登录一次，复用专用 profile：

- profile 目录默认在 `tmp/capture-samples/playwright-profile/`
- 不使用系统 Chrome 真实 profile

如果你只是想快速种出一个可用的研究 profile，也可以直接用当前纯 HTTP 登录链写入本地 profile：

```bash
.venv/bin/python scripts/bootstrap_yeusoft_playwright_profile.py
```

这一步只是给研究用浏览器写入登录态，正式抓取主链仍然保持纯 HTTP。

当前 runner 也会在发现 profile 内缺少有效本地登录态时，自动用这条纯 HTTP 登录链补种研究用 localStorage，再推进到业务页。

对于样本/截图里的“分析变体页”，当前第一轮页面研究采用：

- 打开线上真实父菜单页
- manifest 保留原始研究标题
- 同时记录 `menu_target_title`、`menu_root_name`、`variant_label`、`variant_of`

也就是说，像 `库存总和分析-按年份季节` 这类页面，不再要求线上必须存在同名菜单，而是挂到真实父页面 `库存综合分析` 下做一次变体研究。

第二轮单变量深挖继续建立在这套映射之上：

- 真实菜单仍然只打开一次
- 研究标题继续保留样本里的名字
- 单变量探测改用浏览器会话内的 authenticated fetch
- 每次只改一个参数，不做组合爆炸

在把状态板里的“全域”理解成“当前账号可见全域”之前，还需要先跑一次菜单覆盖审计：

- 导出当前账号完整菜单树
- 逐个可点击页面尝试打开
- 记录哪些页面已覆盖、哪些页面 visible_but_untracked、哪些页面 visible_but_failed
- 把 unknown page 以占位 route 的形式写回状态板

## 4. 运行页面研究

默认会从：

- `tmp/capture-samples/report_api_samples.md`
- `tmp/capture-samples/API-images/`

构建页面 registry。

运行命令：

```bash
.venv/bin/python scripts/run_yeusoft_page_research.py
```

菜单覆盖审计命令：

```bash
.venv/bin/python scripts/run_yeusoft_menu_coverage_audit.py \
  --headless \
  --skip-screenshots
```

这条命令会输出：

- 原始菜单树与逐页 manifest：`output/playwright/yeusoft-menu-coverage/<timestamp>/`
- 结构化审计结果：`tmp/capture-samples/analysis/menu-coverage-audit-<timestamp>.json`

状态板脚本会自动读取最新的 `menu-coverage-audit-*.json`，把：

- `menu_path`
- `coverage_status`
- `coverage_confidence`
- unknown page 占位 route

回写到 `docs/erp/api-maturity-board.md`。

常用参数：

```bash
.venv/bin/python scripts/run_yeusoft_page_research.py \
  --only 销售清单 \
  --only 库存明细统计

.venv/bin/python scripts/run_yeusoft_page_research.py \
  --limit 5

.venv/bin/python scripts/run_yeusoft_page_research.py \
  --headless
```

只补当前菜单覆盖审计发现的 unknown page：

```bash
.venv/bin/python scripts/run_yeusoft_page_research.py \
  --headless \
  --skip-screenshots \
  --unknown-pages-only
```

这条命令会把最新 `menu-coverage-audit-*.json` 里的 `visible_but_untracked` 页面并入研究 runner，跑完后再重跑：

```bash
.venv/bin/python scripts/run_yeusoft_menu_coverage_audit.py \
  --headless \
  --skip-screenshots

.venv/bin/python scripts/build_erp_api_maturity_board.py
```

如果一切正常，状态板里的 `visible_but_untracked` 应该降到 `0`，unknown 占位项会被真实路线替换。

第二轮销售 + 库存单变量深挖：

```bash
.venv/bin/python scripts/run_yeusoft_page_research.py \
  --headless \
  --skip-screenshots \
  --probe-target sales_inventory
```

这条命令当前会覆盖：

- `销售清单`
- `零售明细统计`
- `库存明细统计`
- `出入库单据`
- `库存总和分析-*`
- `库存综合分析-*`

如果要把销售页的页面研究结论和纯 HTTP 回证收成一份闭环证据，再跑：

```bash
.venv/bin/python scripts/analyze_yeusoft_sales_evidence_chain.py
```

这条命令会读取：

- 最新 `yeusoft-page-research-*.json`
- `report_api_samples.md`
- 当前账号的纯 HTTP 登录链

并输出：

- `_1 / SelSaleReport` 与 `_2 / GetDIYReportData` 的头/行路线结论
- `sale_no / sale_date / operator / vip_card_no` 的关联键统计
- `parameter.Tiem / BeginDate / EndDate / Depart` 的 HTTP 语义回证
- `SelDeptSaleList` 的分页差异与对账摘要
- 自动整理后的 `issue_flags`

## 5. 输出目录

原始浏览器证据输出到：

- `output/playwright/yeusoft-research/<timestamp>/`

每个页面至少包含：

- `manifest.json`
- `network/response-*.json|txt`
- 页面截图

结构化归纳结果同时输出到：

- `tmp/capture-samples/analysis/yeusoft-page-research-<timestamp>.json`

## 6. 后处理

如果只想对已有研究产物做二次归纳，可以单独跑：

```bash
.venv/bin/python scripts/postprocess_yeusoft_page_research.py
```

或者指定某次运行目录：

```bash
.venv/bin/python scripts/postprocess_yeusoft_page_research.py \
  --run-dir output/playwright/yeusoft-research/<timestamp>
```

## 7. 当前第一版能力

第一版已经支持：

- 持久化 profile 复用登录态
- 自动打开已知报表/查询页面
- 记录页面动作、网络请求、响应摘要和本地截图
- 对 `销售清单` 这类多粒度菜单给出结构化总结
- 输出主源候选、结果快照候选、分页/枚举线索和推荐抓取策略

第二轮当前已支持：

- 在同一 manifest 里记录 `baseline_request_signature`
- 记录 `single_variable_probe_results`
- 归纳 `parameter_semantics`
- 对销售菜单给出 `grain_route` 和 `candidate_join_keys`
- 对库存枚举给出“切视图 / 切数据范围”的结构化判断

第一版暂不承诺：

- 自动完成所有复杂筛选器的 UI 操作
- 自动登录
- 多角色并行研究

## 8. 和纯 HTTP 主线的关系

页面研究链回答的是：

1. 页面到底触发了哪些接口
2. 哪些参数随页面动作变化
3. 这些变化是在切视图还是切数据范围
4. 哪些接口值得升级到纯 HTTP 正式抓取

只有当页面研究把接口、参数、分页和枚举语义确认清楚之后，才允许把对应接口升级进：

- `scripts/fetch_yeusoft_report_payloads.py`
- `capture` 主链
- `serving` 投影层
