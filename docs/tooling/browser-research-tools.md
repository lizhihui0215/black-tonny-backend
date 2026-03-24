# 浏览器研究工具说明

## 1. 这份文档的作用

这份文档只说明 `black-tonny-backend` 仓库里的通用浏览器研究工具边界。

它回答的是：

- Playwright 研究链是干什么的
- profile 放在哪里
- 研究 runner 会产出什么
- 什么时候该用浏览器研究，什么时候应回落纯 HTTP

Yeusoft 专项研究流程、页面列表和命令细节，继续以：

- [ERP 页面研究运行说明](../erp/page-research-runbook.md)

为准。

## 2. 定位

浏览器研究链当前固定定位为：

- 接口发现工具
- 参数还原工具
- 页面动作到网络请求的证据采集工具

不是：

- 正式定时抓取链
- `capture` 主链运行时依赖
- `serving` 投影生成器

正式链路仍然是：

- 纯 HTTP 抓取
- `capture` 原始留痕
- `serving` 可演进投影

## 3. 常见组件

当前常用组件包括：

- Playwright Chromium
- 专用 research profile
- 页面研究 runner
- 菜单覆盖审计 runner
- 后处理脚本

这些组件都只服务研究和证据收集，不直接决定业务口径。

## 4. 常见目录

研究 profile 默认放在：

- `tmp/capture-samples/playwright-profile/`

原始浏览器证据通常输出到：

- `output/playwright/yeusoft-research/<timestamp>/`
- `output/playwright/yeusoft-menu-coverage/<timestamp>/`

结构化 analysis 通常输出到：

- `tmp/capture-samples/analysis/`

## 5. 推荐使用场景

适合使用浏览器研究的时候：

- 你需要确认某个页面到底触发了哪些接口
- 你需要确认单一筛选项改变了哪些请求参数
- 你需要确认页面里隐藏的 `menuid/gridid/type/datetype/stockflag` 等参数来源
- 你需要做当前账号可见全域的菜单覆盖审计

不适合使用浏览器研究的时候：

- 你已经确认了接口和参数，只需要正式抓取
- 你要定义正式业务口径
- 你要写 `capture` 主链和 `serving` 投影逻辑

## 6. 推荐命令

安装 research 依赖：

```bash
.venv/bin/pip install -e '.[research]'
.venv/bin/python -m playwright install chromium
```

补种研究用 profile：

```bash
.venv/bin/python scripts/bootstrap_yeusoft_playwright_profile.py
```

跑页面研究：

```bash
.venv/bin/python scripts/run_yeusoft_page_research.py
```

跑菜单覆盖审计：

```bash
.venv/bin/python scripts/run_yeusoft_menu_coverage_audit.py \
  --headless \
  --skip-screenshots
```

只做已有产物的后处理：

```bash
.venv/bin/python scripts/postprocess_yeusoft_page_research.py
```

## 7. 使用边界

固定规则：

- 页面研究结论必须再经纯 HTTP 回证，才有资格进入主链准入判断
- 浏览器证据可以解释参数来源，但不能直接替代正式抓取结果
- 浏览器研究发现的新路线，先进入研究状态，不直接进入 `capture`

## 8. 和 ERP 文档的关系

工具文档负责解释“怎么用工具”。

ERP 文档负责解释：

- 业务边界
- 接口可信度
- 路线成熟度
- 主链准入顺序

推荐读法：

1. 先看这里，确认浏览器研究是否适合当前任务
2. 再看 [ERP 页面研究运行说明](../erp/page-research-runbook.md)，执行 Yeusoft 专项流程
3. 最后回到 [ERP API 成熟度总览](../erp/api-maturity-board.md)，确认路线状态
