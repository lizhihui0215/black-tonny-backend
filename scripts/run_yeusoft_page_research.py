#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.erp_research_service import analyze_response_payload
from app.services.research.menu_coverage import load_latest_menu_coverage_audit
from app.services.research.page_research import (
    DEFAULT_QUERY_DATE_RANGE,
    INTERACTIVE_TEXT_SELECTOR,
    SECOND_ROUND_PROBE_TARGETS,
    build_menu_lookup,
    build_menu_coverage_registry_entries,
    build_page_manifest_summary,
    build_page_research_registry,
    build_page_scope_action_texts,
    build_page_scope_texts,
    build_single_variable_probe_cases,
    build_unknown_page_registry_entries,
    diff_payload_paths,
    extract_endpoint_name,
    get_probe_target_titles,
    is_interesting_endpoint,
    list_report_menu_items,
    list_menu_items,
    load_page_research_manifests,
    summarize_page_manifests,
)
from scripts.bootstrap_yeusoft_playwright_profile import build_local_storage_seed
from scripts.fetch_yeusoft_report_payloads import README_PATH


LOCAL_TZ = ZoneInfo("Asia/Shanghai")
SITE_URL = "https://jypos.yeusoft.net/"
DEFAULT_REPORT_DOC = PROJECT_ROOT / "tmp" / "capture-samples" / "report_api_samples.md"
DEFAULT_API_IMAGES_DIR = PROJECT_ROOT / "tmp" / "capture-samples" / "API-images"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "output" / "playwright" / "yeusoft-research"
DEFAULT_PROFILE_DIR = PROJECT_ROOT / "tmp" / "capture-samples" / "playwright-profile"
DEFAULT_ANALYSIS_ROOT = PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"
NETWORK_WAIT_MS = 2500
ENTRY_DATE_RANGE_HINTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "门店盘点单": (
        "store-stocktaking-evidence-chain-*.json",
        ("store_stocktaking", "capture_parameter_plan", "baseline_payload"),
    ),
}


def now_local() -> datetime:
    return datetime.now(LOCAL_TZ)


def should_capture_network_url(url: str, *, capture_all_network: bool) -> bool:
    if is_interesting_endpoint(url):
        return True
    if not capture_all_network:
        return False
    return "yeusoft.net/" in url and any(segment in url for segment in ("/JyApi/", "/eposapi/", "/FxErpApi/"))


def safe_json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")


def sanitize_filename(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value).strip("_")[:80] or "artifact"


def compact_date_to_iso(value: Any) -> str | None:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return None


def _descend_mapping(payload: Any, path: tuple[str, ...]) -> Any:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def resolve_entry_date_range(
    entry,
    *,
    default_start: str,
    default_end: str,
    analysis_root: Path,
) -> tuple[str, str]:
    hint = ENTRY_DATE_RANGE_HINTS.get(str(getattr(entry, "title", "") or ""))
    if not hint:
        return default_start, default_end
    pattern, path = hint
    candidates = sorted(analysis_root.glob(pattern))
    if not candidates:
        return default_start, default_end
    try:
        payload = json.loads(candidates[-1].read_text("utf-8"))
    except Exception:
        return default_start, default_end
    baseline_payload = _descend_mapping(payload, path)
    if not isinstance(baseline_payload, dict):
        return default_start, default_end
    start = compact_date_to_iso(baseline_payload.get("bdate")) or default_start
    end = compact_date_to_iso(baseline_payload.get("edate")) or default_end
    return start, end


def read_member(obj: Any, name: str, default: Any = None) -> Any:
    value = getattr(obj, name, default)
    if callable(value):
        try:
            return value()
        except TypeError:
            return value
    return value


def import_playwright():
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - runtime guidance only
        raise RuntimeError(
            "当前环境缺少 Python Playwright。请先安装 research 依赖，并执行 `python -m playwright install chromium`。"
        ) from exc
    return sync_playwright, PlaywrightTimeoutError


def extract_auth_context(page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const parseJson = (value) => {
            try { return JSON.parse(value || '{}'); } catch { return {}; }
          };
          const loginData = parseJson(localStorage.getItem('yis_pc_logindata'));
          return {
            apiUrl: localStorage.getItem('yisapiurl') || '',
            token: localStorage.getItem('yis_pc_token') || '',
            refreshToken: localStorage.getItem('yis_v2_refreshToken') || '',
            deptCode: loginData.DeptCode || '',
            deptName: loginData.DeptName || '',
            userName: loginData.UserName || '',
            companyCode: loginData.ComCode || '',
          };
        }"""
    )


def seed_login_storage(page) -> dict[str, Any]:
    seed = build_local_storage_seed(Path(README_PATH))
    page.evaluate(
        """(seed) => {
          for (const [key, value] of Object.entries(seed)) {
            if (value === null || value === undefined || value === '') {
              localStorage.removeItem(key);
            } else {
              localStorage.setItem(key, String(value));
            }
          }
        }""",
        seed,
    )
    page.reload(wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2500)
    return extract_auth_context(page)


def ensure_login_ready(page, *, interactive: bool) -> dict[str, Any]:
    auth = extract_auth_context(page)
    if not auth.get("token") or not auth.get("apiUrl"):
        auth = seed_login_storage(page)
    if auth.get("token") and auth.get("apiUrl"):
        return auth
    if interactive:
        print("未检测到有效登录态。请在打开的浏览器窗口完成登录，然后回车继续。")
        input()
        auth = extract_auth_context(page)
    if not auth.get("token") or not auth.get("apiUrl"):
        raise RuntimeError("未检测到有效 Yeusoft 登录态，请先在持久化 profile 中手工登录一次。")
    return auth


def bootstrap_operational_route(page) -> dict[str, Any]:
    return page.evaluate(
        """async () => {
          const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
          const parseJson = (value) => {
            try { return JSON.parse(value || '{}'); } catch { return {}; }
          };
          const app = document.querySelector('#app')?.__vue__?.$children?.[0];
          const route = app?.$route || {};
          const loginData = parseJson(localStorage.getItem('yis_pc_logindata'));
          const result = {
            url: window.location.href,
            routePath: route.path || '',
            routeName: route.name || '',
            applied: false,
            hasUpdateLoginData: typeof app?.updateLoginData === 'function',
            hasUpdateLoginv2Data: typeof app?.updateLoginv2Data === 'function',
            hasJumpAfterLogin: typeof app?.jumpAfterLogin === 'function',
            reason: '',
          };
          if (!app) {
            result.reason = 'app-missing';
            return result;
          }
          const loginShell = route.name === 'yiseposlogin' || route.path === '/';
          if (!loginShell) {
            result.reason = 'already-operational';
            return result;
          }
          if (!Object.keys(loginData).length) {
            result.reason = 'login-data-missing';
            return result;
          }
          try {
            if (typeof app.updateLoginData === 'function') {
              app.updateLoginData(loginData);
              result.applied = true;
            }
            if (typeof app.updateLoginv2Data === 'function') {
              app.updateLoginv2Data(loginData);
              result.applied = true;
            }
            if (typeof app.jumpAfterLogin === 'function') {
              app.jumpAfterLogin();
              result.applied = true;
            }
            await wait(3000);
          } catch (error) {
            result.reason = String(error);
          }
          result.url = window.location.href;
          result.routePath = app?.$route?.path || '';
          result.routeName = app?.$route?.name || '';
          if (!result.reason) {
            result.reason = result.applied ? 'bootstrap-applied' : 'no-login-shell-methods';
          }
          return result;
        }"""
    )


def wait_for_operational_shell(page, timeout_ms: int = 12000) -> dict[str, Any]:
    deadline = now_local().timestamp() + (timeout_ms / 1000)
    last_state: dict[str, Any] = {}
    while now_local().timestamp() < deadline:
        last_state = page.evaluate(
            """() => {
              const app = document.querySelector('#app')?.__vue__?.$children?.[0];
              return {
                href: window.location.href,
                routePath: app?.$route?.path || '',
                routeName: app?.$route?.name || '',
                frameCount: window.frames.length,
              };
            }"""
        )
        if last_state.get("routeName") == "CashierIframeHome" or "/CashierHome" in str(last_state.get("href") or ""):
            return last_state
        page.wait_for_timeout(1000)
    raise RuntimeError(f"业务壳未完成跳转：{json.dumps(last_state, ensure_ascii=False)}")


def iter_operational_frames(page):
    frame_hints = ("/pos_internal/", "#/Cashier", "Cashier")
    yielded_ids: set[int] = set()
    frames = read_member(page, "frames", [])
    for frame in frames:
        try:
            if any(hint in str(read_member(frame, "url", "")) for hint in frame_hints):
                yielded_ids.add(id(frame))
                yield frame
                continue
            has_app = frame.evaluate(
                "() => !!document.querySelector('#app')?.__vue__?.$children?.[0]"
            )
            if has_app:
                yielded_ids.add(id(frame))
                yield frame
        except Exception:
            continue
    main_frame = read_member(page, "main_frame")
    if id(main_frame) not in yielded_ids:
        yield main_frame


def wait_for_operational_frame(page, timeout_ms: int = 15000):
    deadline = now_local().timestamp() + (timeout_ms / 1000)
    while now_local().timestamp() < deadline:
        for frame in iter_operational_frames(page):
            try:
                ready = frame.evaluate(
                    """() => {
                      const app = document.querySelector('#app')?.__vue__?.$children?.[0];
                      return !!app && (typeof app?.addTab === 'function' || typeof app?.jumpPage === 'function' || !!app?.reportArrList);
                    }"""
                )
                if ready:
                    return frame
            except Exception:
                continue
        page.wait_for_timeout(1000)
    raise RuntimeError("未找到可操作的 Yeusoft 业务 frame")


def fetch_menu_list(page) -> list[dict[str, Any]]:
    auth = extract_auth_context(page)
    if not auth.get("apiUrl") or not auth.get("token"):
        return []
    return page.evaluate(
        """async ({ apiUrl, token }) => {
          const response = await fetch(`${apiUrl}/eposapi/YisEposSaleManage/GetMenuList`, {
            method: 'POST',
            headers: {
              'content-type': 'application/json;charset=UTF-8',
              token,
            },
            body: JSON.stringify({ isaution: 'E' }),
          });
          const payload = await response.json();
          return payload.retdata || [];
        }""",
        {"apiUrl": auth["apiUrl"], "token": auth["token"]},
    )


def _build_scope_resolver_js() -> str:
    return """
const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
const isVisible = (node) => {
  if (!node) return false;
  const rect = node.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
};
const describeNode = (node) => {
  if (!node) return 'null';
  const parts = [String(node.tagName || '').toLowerCase()];
  if (node.id) parts.push(`#${node.id}`);
  if (node.className && typeof node.className === 'string') {
    const classes = node.className.split(/\\s+/).filter(Boolean).slice(0, 4);
    if (classes.length) parts.push(`.${classes.join('.')}`);
  }
  return parts.join('');
};
const buttonsSelector = 'button,.el-button,.buttons,.operate-button-group > div,.blue,.orange,li,span,div,a';
const actionSeedSelector = 'button,.el-button,.query_btn,.buttons,.operate-button-group > div,.blue,.orange,a,.el-tabs__item';
const queryButtonSelector = 'button,.el-button,.query_btn,.buttons,.operate-button-group > div,.blue,.orange,a';
const rowSelector = '.el-table__body-wrapper tbody tr,.el-table__body tbody tr,.el-table__row,tbody tr';
const tableSelector = '.el-table,.el-table__body-wrapper,.el-table__body,.el-table__empty-block,table,.vxe-table,.vxe-table--body-wrapper';
const paginationSelector = '.el-pagination,.el-pagination__total,.el-pagination__sizes,.pagination,.pager';
const inputSelector = '.el-date-editor input,.el-range-editor input,input[placeholder*="开始"],input[placeholder*="结束"],input[placeholder*="时间"],input';
const actionLabels = ['查询', '单据确认', '物流信息', '查看明细', '条码记录', '统计损溢', '新增'];
const resolveScopeRoot = (scopeHints) => {
  const wanted = Array.from(new Set(((scopeHints && scopeHints.titleTexts) || []).map(normalize).filter(Boolean)));
  const actionTexts = Array.from(new Set(((scopeHints && scopeHints.actionTexts) || []).map(normalize).filter(Boolean)));
  const titleMatches = Array.from(document.querySelectorAll('*')).filter((node) => {
    if (!isVisible(node)) return false;
    return wanted.includes(normalize(node.textContent));
  });
  const viewportArea = Math.max(window.innerWidth * window.innerHeight, 1);
  const candidates = [];
  const scoreNode = (root, source, depth, matchedText) => {
    if (!root || root === document.body || root === document.documentElement || !isVisible(root)) return;
    const rect = root.getBoundingClientRect();
    const area = rect.width * rect.height;
    const queryCount = Array.from(root.querySelectorAll(queryButtonSelector)).filter((node) => {
      return isVisible(node) && normalize(node.textContent).includes('查询');
    }).length;
    const rowCount = Array.from(root.querySelectorAll(rowSelector)).filter((node) => {
      if (!isVisible(node)) return false;
      const text = normalize(node.textContent);
      return Boolean(text) && !text.includes('暂无数据');
    }).length;
    const tableCount = Array.from(root.querySelectorAll(tableSelector)).filter(isVisible).length;
    const paginationCount = Array.from(root.querySelectorAll(paginationSelector)).filter(isVisible).length;
    const inputCount = Array.from(root.querySelectorAll(inputSelector)).filter(isVisible).length;
    const actionMatches = actionTexts.filter((label) => {
      return Array.from(root.querySelectorAll(actionSeedSelector)).some((node) => {
        return isVisible(node) && normalize(node.textContent).includes(label);
      });
    });
    const titleMatchCount = wanted.filter((label) => normalize(root.textContent).includes(label)).length;
    const noDataCount = normalize(root.textContent).includes('暂无数据') ? 1 : 0;
    let score = 0;
    if (queryCount) score += 20;
    if (rowCount) score += 30 + Math.min(rowCount, 5) * 2;
    if (inputCount) score += Math.min(inputCount, 5);
    if (actionMatches.length) score += 40 + actionMatches.length * 8;
    if (titleMatchCount) score += 6;
    if (tableCount) score += 18 + Math.min(tableCount, 3) * 4;
    if (paginationCount) score += 8;
    if (queryCount && (tableCount || paginationCount)) score += 24;
    if (actionMatches.length && (tableCount || paginationCount)) score += 32;
    if (!tableCount && !paginationCount && actionMatches.length) score -= 16;
    if (noDataCount) score += 4;
    if (area > viewportArea * 0.9) score -= 28;
    if (area > viewportArea * 0.6) score -= 10;
    if (area < viewportArea * 0.03 && !tableCount) score -= 10;
    score -= depth * 2;
    candidates.push({
      root,
      source,
      score,
      depth,
      area,
      queryCount,
      rowCount,
      tableCount,
      paginationCount,
      inputCount,
      actionCount: actionMatches.length,
      actionLabels: actionMatches,
      matchedText,
      rootDesc: describeNode(root),
    });
  };
  for (const titleNode of titleMatches) {
    let current = titleNode;
    let depth = 0;
    while (current && depth < 10) {
      scoreNode(current, 'title_ancestor', depth, normalize(titleNode.textContent));
      current = current.parentElement;
      depth += 1;
    }
  }
  const actionSeedNodes = Array.from(document.querySelectorAll(actionSeedSelector)).filter((node) => {
    if (!isVisible(node)) return false;
    const text = normalize(node.textContent);
    return Boolean(text) && (
      text.includes('查询')
      || actionTexts.some((label) => text.includes(label))
    );
  });
  for (const actionNode of actionSeedNodes) {
    let current = actionNode;
    let depth = 0;
    while (current && depth < 10) {
      scoreNode(current, 'action_ancestor', depth, normalize(actionNode.textContent));
      current = current.parentElement;
      depth += 1;
    }
  }
  const containerSelectors = [
    '.page-container',
    '.main > div',
    '.main',
    '.content > div',
    '.content',
    '.el-tab-pane',
    '.container',
    '.report',
  ];
  const seen = new Set();
  for (const selector of containerSelectors) {
    for (const node of document.querySelectorAll(selector)) {
      if (!isVisible(node)) continue;
      if (seen.has(node)) continue;
      seen.add(node);
      scoreNode(node, 'container_scan', 0, '');
    }
  }
  candidates.sort((left, right) => (
    right.score - left.score
    || left.depth - right.depth
    || left.area - right.area
  ));
  return candidates[0] || null;
};
"""


def resolve_page_scope(
    frame,
    *,
    scope_texts: list[str] | tuple[str, ...] | None,
    action_texts: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    return frame.evaluate(
        """(scopeTexts) => {
"""
        + _build_scope_resolver_js()
        + """
          const scoped = resolveScopeRoot(scopeTexts);
          if (!scoped) {
            return {
              matched: false,
              scope_texts: (scopeTexts && scopeTexts.titleTexts) || [],
              action_texts: (scopeTexts && scopeTexts.actionTexts) || [],
            };
          }
          return {
            matched: true,
            scope_texts: (scopeTexts && scopeTexts.titleTexts) || [],
            action_texts: (scopeTexts && scopeTexts.actionTexts) || [],
            matched_text: scoped.matchedText,
            root_desc: scoped.rootDesc,
            source: scoped.source,
            score: scoped.score,
            depth: scoped.depth,
            row_count: scoped.rowCount,
            table_count: scoped.tableCount,
            pagination_count: scoped.paginationCount,
            query_count: scoped.queryCount,
            input_count: scoped.inputCount,
            action_count: scoped.actionCount,
            matched_action_labels: scoped.actionLabels,
          };
        }""",
        {
            "titleTexts": list(scope_texts or []),
            "actionTexts": list(action_texts or []),
        },
    )


def click_exact_text(
    frame,
    text: str,
    *,
    scope_texts: list[str] | tuple[str, ...] | None = None,
    action_texts: list[str] | tuple[str, ...] | None = None,
) -> bool:
    return bool(
        frame.evaluate(
            """([selector, expectedText, scopeTexts]) => {
"""
            + _build_scope_resolver_js()
            + """
              const scoped = resolveScopeRoot(scopeTexts);
              const roots = scoped?.root ? [scoped.root, document] : [document];
              for (const searchRoot of roots) {
                const candidates = Array.from(searchRoot.querySelectorAll(selector))
                  .filter((item) => {
                    if (!isVisible(item)) return false;
                    const content = normalize(item.textContent);
                    return content === expectedText || content.includes(expectedText);
                  })
                  .sort((left, right) => normalize(left.textContent).length - normalize(right.textContent).length);
                const target = candidates[0];
                if (!target) continue;
                target.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                return true;
              }
              return false;
            }""",
            [INTERACTIVE_TEXT_SELECTOR, text, {"titleTexts": list(scope_texts or []), "actionTexts": list(action_texts or [])}],
        )
    )


def reveal_menu_root(frame, page, root_name: str) -> None:
    frame.evaluate(
        """() => {
          const app = document.querySelector('#app')?.__vue__?.$children?.[0];
          if (app) app.showSilder = true;
        }"""
    )
    page.wait_for_timeout(1200)
    click_exact_text(frame, root_name)
    page.wait_for_timeout(800)


def ensure_menu_group(frame, page, group_name: str) -> None:
    if not group_name:
        return
    if click_exact_text(frame, group_name):
        page.wait_for_timeout(600)


def lookup_menu_item(menu_lookup: Mapping[str, dict[str, Any]], entry) -> dict[str, Any] | None:
    root_name = str(entry.menu_root_name or "")
    target_title = str(entry.menu_target_title or entry.canonical_name or entry.title)
    candidates = [
        f"{root_name}::{target_title}",
        f"{root_name}::{entry.canonical_name}",
        f"{root_name}::{entry.title}",
        target_title,
        entry.canonical_name,
        entry.title,
    ]
    for key in candidates:
        if key and key in menu_lookup:
            return menu_lookup[key]
    return None


def open_report_by_menu_item(frame, page, menu_item: Mapping[str, Any]) -> dict[str, Any]:
    result = frame.evaluate(
        """(menuItemValue) => {
          const app = document.querySelector('#app')?.__vue__?.$children?.[0];
          if (!app) return { ok: false, reason: 'app-missing' };
          if (typeof app.addTab !== 'function') return { ok: false, reason: 'no-addTab' };
          try {
            app.addTab(menuItemValue);
            return {
              ok: true,
              endTitle: app.titleTabsValue || '',
            };
          } catch (error) {
            return { ok: false, reason: String(error) };
          }
        }""",
        dict(menu_item),
    )
    if not result.get("ok"):
        reveal_menu_root(frame, page, str(menu_item.get("rootName") or ""))
        ensure_menu_group(frame, page, str(menu_item.get("groupName") or ""))
        if not click_exact_text(frame, str(menu_item.get("canonicalName") or menu_item.get("FuncName") or "")):
            raise RuntimeError(f"未能通过菜单打开页面：{menu_item.get('FuncName')}")
    page.wait_for_timeout(2500)
    return result


def capture_visible_controls(
    frame,
    *,
    scope_texts: list[str] | tuple[str, ...] | None = None,
    action_texts: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    return frame.evaluate(
        """([selector, scopeTexts]) => {
"""
        + _build_scope_resolver_js()
        + """
          const scoped = resolveScopeRoot(scopeTexts);
          const searchRoot = scoped?.root || document;
          return Array.from(searchRoot.querySelectorAll(selector))
            .filter((item) => {
              return isVisible(item);
            })
            .map((item) => ({
              tag: item.tagName.toLowerCase(),
              text: normalize(item.textContent),
              className: item.className || '',
            }))
            .filter((item) => item.text)
            .slice(0, 200);
        }""",
        [INTERACTIVE_TEXT_SELECTOR, {"titleTexts": list(scope_texts or []), "actionTexts": list(action_texts or [])}],
    )


def capture_component_state(
    frame,
    *,
    scope_texts: list[str] | tuple[str, ...] | None = None,
    action_texts: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    return frame.evaluate(
        """(scopeTexts) => {
"""
        + _build_scope_resolver_js()
        + """
          const normalizeText = (value) => normalize(String(value || '')).slice(0, 200);
          const seen = new Set();
          const componentSummaries = [];

          const summarizeCollection = (key, value) => {
            if (Array.isArray(value)) {
              if (!value.length) return null;
              const sample = value[0];
              if (sample && typeof sample === 'object' && !Array.isArray(sample)) {
                return {
                  field: key,
                  kind: 'object_array',
                  length: value.length,
                  sample_keys: Object.keys(sample).slice(0, 8),
                };
              }
              return {
                field: key,
                kind: 'scalar_array',
                length: value.length,
                sample_values: value.slice(0, 5).map((item) => normalizeText(item)),
              };
            }
            if (!value || typeof value !== 'object') return null;
            if (Array.isArray(value.Data) && value.Data.length) {
              const sample = value.Data[0];
              return {
                field: key,
                kind: 'nested_data_array',
                length: value.Data.length,
                sample_keys: sample && typeof sample === 'object' ? Object.keys(sample).slice(0, 8) : [],
                count_hint: value.DataCount || value.Count || null,
              };
            }
            for (const nestedKey of ['list', 'rows', 'tableData', 'gridData']) {
              const nestedValue = value[nestedKey];
              if (Array.isArray(nestedValue) && nestedValue.length) {
                const sample = nestedValue[0];
                return {
                  field: `${key}.${nestedKey}`,
                  kind: 'nested_named_array',
                  length: nestedValue.length,
                  sample_keys: sample && typeof sample === 'object' ? Object.keys(sample).slice(0, 8) : [],
                };
              }
            }
            return null;
          };

          const summarizeVm = (vm, source) => {
            if (!vm || seen.has(vm)) return;
            seen.add(vm);
            const keys = Object.keys(vm)
              .filter((key) => !key.startsWith('$') && !key.startsWith('_'))
              .slice(0, 80);
            const collections = [];
            const emptyCollectionHints = [];
            const scalars = {};
            for (const key of keys) {
              let value;
              try {
                value = vm[key];
              } catch (error) {
                continue;
              }
              const collection = summarizeCollection(key, value);
              if (collection) {
                collections.push(collection);
                continue;
              }
              const rowLikeKey = /(data|list|row|grid|table|detail|item|record|source)/i.test(key);
              if (rowLikeKey) {
                if (Array.isArray(value) && !value.length) {
                  emptyCollectionHints.push({
                    field: key,
                    kind: 'empty_array',
                    length: 0,
                  });
                  continue;
                }
                if (value && typeof value === 'object') {
                  if (Array.isArray(value.Data) && !value.Data.length) {
                    emptyCollectionHints.push({
                      field: `${key}.Data`,
                      kind: 'empty_nested_data',
                      length: 0,
                      count_hint: value.DataCount || value.Count || null,
                    });
                    continue;
                  }
                  for (const nestedKey of ['list', 'rows', 'tableData', 'gridData']) {
                    const nestedValue = value[nestedKey];
                    if (Array.isArray(nestedValue) && !nestedValue.length) {
                      emptyCollectionHints.push({
                        field: `${key}.${nestedKey}`,
                        kind: 'empty_named_array',
                        length: 0,
                      });
                      break;
                    }
                  }
                }
              }
              if (['page', 'pageSize', 'pageIndex', 'currentPage', 'total', 'totalCount', 'count', 'loading'].includes(key)) {
                if (value === null || value === undefined) continue;
                if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
                  scalars[key] = value;
                }
              }
            }
            componentSummaries.push({
              source,
              name: vm.$options?.name || vm.$vnode?.tag || vm.$options?._componentTag || '',
              keys_sample: keys.slice(0, 20),
              non_empty_collections: collections.slice(0, 12),
              empty_collection_hints: emptyCollectionHints.slice(0, 12),
              scalar_hints: scalars,
            });
          };

          const pushCandidateNode = (node, source) => {
            if (!node) return;
            const vm = node.__vue__ || null;
            if (vm) summarizeVm(vm, source);
          };

          const scoped = resolveScopeRoot(scopeTexts);
          const scopedRoot = scoped?.root || null;
          if (scopedRoot) {
            let current = scopedRoot;
            let depth = 0;
            while (current && depth < 6) {
              pushCandidateNode(current, depth === 0 ? 'scope_root' : `scope_ancestor_${depth}`);
              current = current.parentElement;
              depth += 1;
            }
            const descendants = Array.from(scopedRoot.querySelectorAll('*')).slice(0, 400);
            descendants.forEach((node, index) => {
              if (index < 80 || node.matches('.vxe-grid,.vxe-table,.el-table,.reportTable-warp,.content,.page-container')) {
                pushCandidateNode(node, `scope_descendant_${index}`);
              }
            });
          }

          const app = document.querySelector('#app')?.__vue__?.$children?.[0];
          if (app) {
            summarizeVm(app, 'app_root');
            Array.from(app.$children || []).slice(0, 12).forEach((child, index) => summarizeVm(child, `app_child_${index}`));
          }

          componentSummaries.sort((left, right) => {
            const leftScore = (left.non_empty_collections || []).reduce((sum, item) => sum + Number(item.length || 0), 0);
            const rightScore = (right.non_empty_collections || []).reduce((sum, item) => sum + Number(item.length || 0), 0);
            return rightScore - leftScore;
          });

          const emptyText = Array.from(document.querySelectorAll('.vxe-table--empty-content,.el-table__empty-text,[class*=empty]'))
            .map((node) => normalizeText(node.textContent))
            .filter(Boolean)
            .slice(0, 8);
          const pagerText = Array.from(document.querySelectorAll('.vxe-pager--total,.el-pagination__total,.vxe-pager--wrapper,.el-pagination'))
            .map((node) => normalizeText(node.textContent))
            .filter(Boolean)
            .slice(0, 8);

          return {
            component_count: componentSummaries.length,
            top_components: componentSummaries.slice(0, 12),
            empty_texts: emptyText,
            pager_texts: pagerText,
          };
        }""",
        {
            "titleTexts": list(scope_texts or []),
            "actionTexts": list(action_texts or []),
        },
    )


def capture_step_ui_state(
    frame,
    *,
    scope_texts: list[str] | tuple[str, ...] | None = None,
    action_texts: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    return frame.evaluate(
        """(scopeTexts) => {
"""
        + _build_scope_resolver_js()
        + """
          const scoped = resolveScopeRoot(scopeTexts);
          const roots = scoped?.root ? [scoped.root, document] : [document];
          const isGridRowCandidate = (row) => {
            if (!isVisible(row)) return false;
            if (row.closest('.el-picker-panel, .el-date-picker, .el-date-range-picker, .el-time-panel, .el-month-table, .el-year-table, .el-date-table')) {
              return false;
            }
            const text = normalize(row.textContent);
            if (!text || text.includes('暂无数据')) return false;
            if (/^日一二三四五六$/.test(text)) return false;
            return true;
          };
          const rowSelectors = [
            '.vxe-table--body tbody tr',
            '.el-table__body-wrapper tbody tr',
            '.el-table__body tbody tr',
            '.el-table__row',
            'tbody tr',
          ];
          const dialogSelector = '.el-dialog,.vxe-modal--wrapper,.el-drawer,.drawer,.modal';
          const buttonSelector = 'button,.el-button,.buttons,li,div,span,a';
          const pickRows = (root) => {
            for (const selector of rowSelectors) {
              const rows = Array.from(root.querySelectorAll(selector)).filter(isGridRowCandidate);
              if (rows.length) {
                return {
                  selector,
                  count: rows.length,
                  first_row_text: normalize(rows[0].textContent).slice(0, 200),
                };
              }
            }
            return { selector: null, count: 0, first_row_text: '' };
          };
          const pickDialogs = () => {
            return Array.from(document.querySelectorAll(dialogSelector))
              .filter((node) => isVisible(node))
              .map((node) => ({
                className: node.className || '',
                text: normalize(node.textContent).slice(0, 200),
              }))
              .slice(0, 8);
          };
          const pickDecisionButtons = () => {
            return Array.from(document.querySelectorAll(buttonSelector))
              .filter((node) => {
                if (!isVisible(node)) return false;
                const text = normalize(node.textContent);
                return text.includes('确定') || text.includes('取消') || text.includes('保存') || text.includes('关闭');
              })
              .map((node) => ({
                text: normalize(node.textContent).slice(0, 80),
                className: node.className || '',
              }))
              .slice(0, 12);
          };
          for (const root of roots) {
            const rowProbe = pickRows(root);
            if (rowProbe.count || root === document) {
              return {
                row_probe: rowProbe,
                dialogs: pickDialogs(),
                decision_buttons: pickDecisionButtons(),
              };
            }
          }
          return {
            row_probe: { selector: null, count: 0, first_row_text: '' },
            dialogs: pickDialogs(),
            decision_buttons: pickDecisionButtons(),
          };
        }""",
        {
            "titleTexts": list(scope_texts or []),
            "actionTexts": list(action_texts or []),
        },
    )


def try_set_date_range(
    frame,
    start_date: str,
    end_date: str,
    *,
    scope_texts: list[str] | tuple[str, ...] | None = None,
    action_texts: list[str] | tuple[str, ...] | None = None,
) -> bool:
    return bool(
        frame.evaluate(
            """([startDate, endDate, scopeTexts]) => {
"""
            + _build_scope_resolver_js()
            + """
              const scopedRoot = resolveScopeRoot(scopeTexts)?.root || null;
              const roots = scopedRoot ? [scopedRoot, document] : [document];
              const selectors = [
                '.el-date-editor input',
                '.el-range-input',
                '.el-range-editor input',
                "input[placeholder*='开始']",
                "input[placeholder*='结束']",
                "input[placeholder*='日期']",
                "input[placeholder*='时间']",
              ];
              for (const root of roots) {
                const inputs = Array.from(root.querySelectorAll(selectors.join(',')))
                  .filter((input) => {
                    return isVisible(input);
                  });
                if (inputs.length < 2) continue;
                inputs[0].focus?.();
                inputs[0].value = '';
                inputs[0].dispatchEvent(new Event('input', { bubbles: true }));
                inputs[0].value = startDate;
                inputs[0].dispatchEvent(new Event('input', { bubbles: true }));
                inputs[0].dispatchEvent(new Event('change', { bubbles: true }));
                inputs[1].focus?.();
                inputs[1].value = '';
                inputs[1].dispatchEvent(new Event('input', { bubbles: true }));
                inputs[1].value = endDate;
                inputs[1].dispatchEvent(new Event('input', { bubbles: true }));
                inputs[1].dispatchEvent(new Event('change', { bubbles: true }));
                inputs[1].dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
                return true;
              }
              return false;
            }""",
            [start_date, end_date, {"titleTexts": list(scope_texts or []), "actionTexts": list(action_texts or [])}],
        )
    )


def click_query_button(
    frame,
    *,
    scope_texts: list[str] | tuple[str, ...] | None = None,
    action_texts: list[str] | tuple[str, ...] | None = None,
) -> bool:
    return bool(
        frame.evaluate(
            """(scopeTexts) => {
"""
            + _build_scope_resolver_js()
            + """
              const scopedRoot = resolveScopeRoot(scopeTexts)?.root || null;
              const roots = scopedRoot ? [scopedRoot, document] : [document];
              const selector = [
                'button',
                '.el-button',
                '.query_btn',
                '.buttons',
                '.operate-button-group > div',
                '.blue',
                '.orange',
                'a',
              ].join(',');
              for (const root of roots) {
                const candidates = Array.from(root.querySelectorAll(selector))
                  .filter((item) => {
                    const rect = item.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                  });
                const target = candidates.find((item) => normalize(item.textContent) === '查询')
                  || candidates.find((item) => normalize(item.textContent).includes('查询'));
                if (!target) continue;
                target.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                return true;
              }
              return false;
            }""",
            {"titleTexts": list(scope_texts or []), "actionTexts": list(action_texts or [])},
        )
    )


def select_first_grid_row(
    frame,
    *,
    scope_texts: list[str] | tuple[str, ...] | None = None,
    action_texts: list[str] | tuple[str, ...] | None = None,
) -> bool:
    return bool(
        frame.evaluate(
            """(scopeTexts) => {
"""
            + _build_scope_resolver_js()
            + """
              const isGridRowCandidate = (row) => {
                if (!isVisible(row)) return false;
                if (row.closest('.el-picker-panel, .el-date-picker, .el-date-range-picker, .el-time-panel, .el-month-table, .el-year-table, .el-date-table')) {
                  return false;
                }
                const text = normalize(row.textContent);
                if (!text || text.includes('暂无数据')) return false;
                if (/^日一二三四五六$/.test(text)) return false;
                return true;
              };
              const scopedRoot = resolveScopeRoot(scopeTexts)?.root || null;
              const roots = scopedRoot ? [scopedRoot, document] : [document];
              const candidates = [
                '.vxe-table--body tbody tr',
                '.vxe-body--row',
                '.el-table__body-wrapper tbody tr',
                '.el-table__body tbody tr',
                '.el-table__row',
                'tbody tr',
              ];
              for (const root of roots) {
                for (const selector of candidates) {
                  const rows = Array.from(root.querySelectorAll(selector)).filter(isGridRowCandidate);
                  const row = rows[0];
                  if (row) {
                    row.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                    return true;
                  }
                }
              }
              return false;
            }""",
            {"titleTexts": list(scope_texts or []), "actionTexts": list(action_texts or [])},
        )
    )


class NetworkCollector:
    def __init__(self, page, page_dir: Path, *, capture_all_network: bool = False):
        self.page = page
        self.page_dir = page_dir
        self.network_dir = page_dir / "network"
        self.network_dir.mkdir(parents=True, exist_ok=True)
        self.requests: list[dict[str, Any]] = []
        self.responses: list[dict[str, Any]] = []
        self.capture_all_network = capture_all_network
        self._request_id_counter = 0
        self._request_map: dict[int, int] = {}
        self.current_action_key = "bootstrap"
        self._request_handler = self._on_request
        self._response_handler = self._on_response
        self.page.on("request", self._request_handler)
        self.page.on("response", self._response_handler)

    def close(self) -> None:
        try:
            self.page.remove_listener("request", self._request_handler)
        except Exception:
            try:
                self.page.off("request", self._request_handler)
            except Exception:
                pass
        try:
            self.page.remove_listener("response", self._response_handler)
        except Exception:
            try:
                self.page.off("response", self._response_handler)
            except Exception:
                pass

    def set_action(self, action_key: str) -> None:
        self.current_action_key = action_key

    def snapshot_counts(self) -> tuple[int, int]:
        return len(self.requests), len(self.responses)

    def collect_since(self, counts: tuple[int, int]) -> dict[str, list[dict[str, Any]]]:
        request_count, response_count = counts
        return {
            "requests": self.requests[request_count:],
            "responses": self.responses[response_count:],
        }

    def _on_request(self, request) -> None:
        url = str(read_member(request, "url", ""))
        if not should_capture_network_url(url, capture_all_network=self.capture_all_network):
            return
        self._request_id_counter += 1
        request_id = self._request_id_counter
        self._request_map[id(request)] = request_id
        try:
            post_data = read_member(request, "post_data_json")
        except Exception:
            post_data = read_member(request, "post_data")
        self.requests.append(
            {
                "id": request_id,
                "action_key": self.current_action_key,
                "captured_at": now_local().isoformat(),
                "method": str(read_member(request, "method", "")),
                "url": url,
                "post_data": post_data,
            }
        )

    def _on_response(self, response) -> None:
        url = str(read_member(response, "url", ""))
        if not should_capture_network_url(url, capture_all_network=self.capture_all_network):
            return
        response_request = read_member(response, "request")
        request_id = self._request_map.get(id(response_request))
        body: Any
        suffix = "json"
        try:
            body = response.json()
        except Exception:
            try:
                body = response.text()
                suffix = "txt"
            except Exception:
                body = "<unreadable>"
                suffix = "txt"
        endpoint = sanitize_filename(extract_endpoint_name(url) or "response")
        response_id = len(self.responses) + 1
        body_path = self.network_dir / f"response-{response_id:03d}-{endpoint}.{suffix}"
        if suffix == "json":
            safe_json_dump(body_path, body)
        else:
            body_path.write_text(str(body), "utf-8")
        response_summary = analyze_response_payload(body) if suffix == "json" else analyze_response_payload(str(body))
        self.responses.append(
            {
                "id": response_id,
                "request_id": request_id,
                "action_key": self.current_action_key,
                "captured_at": now_local().isoformat(),
                "status": int(read_member(response, "status", 0) or 0),
                "url": url,
                "body_path": str(body_path),
                "response_summary": response_summary,
            }
        )


def build_step_delta(
    before_delta: dict[str, list[dict[str, Any]]],
    previous_requests: list[dict[str, Any]],
    *,
    reference_payloads: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_requests = before_delta["requests"]
    current_responses = before_delta["responses"]
    previous_by_endpoint = {
        extract_endpoint_name(str(item.get("url") or "")): item
        for item in reversed(previous_requests)
        if item.get("post_data") is not None
    }
    reference_payloads = reference_payloads or {}
    request_diffs = []
    for request in current_requests:
        endpoint = extract_endpoint_name(str(request.get("url") or ""))
        previous_request = previous_by_endpoint.get(endpoint)
        if endpoint in reference_payloads:
            previous_payload = reference_payloads[endpoint]
        elif previous_request:
            previous_payload = previous_request.get("post_data")
        else:
            previous_payload = None
        if request.get("post_data") is None:
            continue
        if previous_payload is not None:
            diff = diff_payload_paths(previous_payload, request.get("post_data"))
        else:
            diff = {"changed_paths": [], "changed_count": 0}
        request_diffs.append(
            {
                "endpoint": endpoint,
                "url": request.get("url"),
                **diff,
            }
        )
    response_fingerprints = [
        {
            "endpoint": extract_endpoint_name(str(item.get("url") or "")),
            "status": item.get("status"),
            "row_count": (item.get("response_summary") or {}).get("row_count"),
            "columns_signature": (item.get("response_summary") or {}).get("columns_signature"),
            "row_set_signature": (item.get("response_summary") or {}).get("row_set_signature"),
            "is_data_endpoint": bool((item.get("response_summary") or {}).get("row_count") is not None)
            and extract_endpoint_name(str(item.get("url") or "")) not in {
                "GetMenuList",
                "GetConfiguration",
                "GetFilterContentData",
                "GetControlData",
                "GetViewGridList",
            },
        }
        for item in current_responses
    ]
    return {
        "request_count": len(current_requests),
        "response_count": len(current_responses),
        "request_diffs": request_diffs,
        "response_fingerprints": response_fingerprints,
    }


def perform_authenticated_probe_fetch(page, *, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    return page.evaluate(
        """async ({ url, payload }) => {
          const token = localStorage.getItem('yis_pc_token') || '';
          const headers = {
            'content-type': 'application/json;charset=UTF-8',
          };
          if (url.includes('/JyApi/')) {
            headers['Authorization'] = `Bearer ${token}`;
          } else {
            headers['token'] = token;
          }
          const response = await fetch(url, {
            method: 'POST',
            headers,
            body: JSON.stringify(payload),
          });
          return {
            ok: response.ok,
            status: response.status,
            url: response.url,
          };
        }""",
        {"url": url, "payload": payload},
    )


def research_single_page(
    *,
    entry,
    page,
    frame,
    menu_lookup: Mapping[str, dict[str, Any]],
    run_dir: Path,
    start_date: str,
    end_date: str,
    skip_screenshots: bool,
    probe_target: str | None,
    capture_all_network: bool,
) -> dict[str, Any]:
    page_dir = run_dir / entry.slug
    page_dir.mkdir(parents=True, exist_ok=True)
    collector = NetworkCollector(page, page_dir, capture_all_network=capture_all_network)
    manifest: dict[str, Any] = {
        "page": entry.as_dict(),
        "run_context": {
            "started_at": now_local().isoformat(),
            "query_date_range": {"start": start_date, "end": end_date},
        },
        "status": "ok",
        "actions": [],
        "visible_controls": [],
        "network": {"requests": [], "responses": []},
    }
    previous_requests: list[dict[str, Any]] = []
    scope_texts = build_page_scope_texts(entry)
    scope_action_texts = build_page_scope_action_texts(entry)
    query_step = next((step for step in entry.recipe.steps if step.key == "query"), None)

    def run_action(
        action_key: str,
        label: str,
        callback,
        wait_ms: int = NETWORK_WAIT_MS,
        *,
        metadata: dict[str, Any] | None = None,
        reference_payloads: dict[str, Any] | None = None,
    ) -> None:
        nonlocal previous_requests
        collector.set_action(action_key)
        counts = collector.snapshot_counts()
        action_triggered = bool(callback())
        page.wait_for_timeout(wait_ms)
        delta = collector.collect_since(counts)
        step = {
            "key": action_key,
            "label": label,
            "captured_at": now_local().isoformat(),
            "action_triggered": action_triggered,
            **build_step_delta(delta, previous_requests, reference_payloads=reference_payloads),
            "ui_state": capture_step_ui_state(
                frame,
                scope_texts=scope_texts,
                action_texts=scope_action_texts,
            ),
        }
        if not action_triggered:
            step["status"] = "not_triggered"
        if metadata:
            step.update(metadata)
        manifest["actions"].append(step)
        previous_requests = previous_requests + delta["requests"]

    def run_recipe_step(step) -> None:
        action = None
        if step.kind == "click_text" and step.target_text:
            action = lambda step=step: click_exact_text(
                frame,
                step.target_text,
                scope_texts=scope_texts,
                action_texts=scope_action_texts,
            )
        elif step.kind == "select_first_grid_row":
            action = lambda: select_first_grid_row(
                frame,
                scope_texts=scope_texts,
                action_texts=scope_action_texts,
            )
        else:
            return

        performed = False

        def callback() -> bool:
            nonlocal performed
            if performed:
                return True
            performed = True
            return bool(action and action())

        if not callback():
            manifest["actions"].append(
                {
                    "key": step.key,
                    "label": step.label,
                    "captured_at": now_local().isoformat(),
                    "status": "missing_target",
                    "request_count": 0,
                    "response_count": 0,
                    "request_diffs": [],
                    "response_fingerprints": [],
                    "ui_state": capture_step_ui_state(
                        frame,
                        scope_texts=scope_texts,
                        action_texts=scope_action_texts,
                    ),
                    "step_kind": step.kind,
                    "target_text": step.target_text,
                }
            )
            return
        run_action(
            step.key,
            step.label,
            callback,
            wait_ms=step.wait_ms,
            metadata={
                "step_kind": step.kind,
                "target_text": step.target_text,
            },
        )

    try:
        menu_item = lookup_menu_item(menu_lookup, entry)
        if not menu_item:
            raise RuntimeError(f"菜单中未找到页面：{entry.title}")

        run_action("open", "打开页面", lambda: open_report_by_menu_item(frame, page, menu_item))
        if not skip_screenshots:
            page.screenshot(path=str(page_dir / "opened.png"), full_page=True)
        manifest["page_scope"] = resolve_page_scope(
            frame,
            scope_texts=scope_texts,
            action_texts=scope_action_texts,
        )
        manifest["visible_controls"] = capture_visible_controls(
            frame,
            scope_texts=scope_texts,
            action_texts=scope_action_texts,
        )

        if entry.recipe.date_range_applicable:
            run_action(
                "set_date_range",
                "设置日期范围",
                lambda: try_set_date_range(
                    frame,
                    start_date,
                    end_date,
                    scope_texts=scope_texts,
                    action_texts=scope_action_texts,
                ),
                wait_ms=1200,
            )

        if entry.recipe.query_required:
            run_action(
                "query",
                "执行查询",
                lambda: click_query_button(
                    frame,
                    scope_texts=scope_texts,
                    action_texts=scope_action_texts,
                ),
                wait_ms=query_step.wait_ms if query_step else NETWORK_WAIT_MS,
            )
            if not skip_screenshots:
                page.screenshot(path=str(page_dir / "queried.png"), full_page=True)
            manifest["page_scope_after_query"] = resolve_page_scope(
                frame,
                scope_texts=scope_texts,
                action_texts=scope_action_texts,
            )
            manifest["visible_controls_after_query"] = capture_visible_controls(
                frame,
                scope_texts=scope_texts,
                action_texts=scope_action_texts,
            )

        for step in entry.recipe.steps:
            if step.kind in {"open", "query"}:
                continue
            run_recipe_step(step)

        for index, label in enumerate(entry.recipe.variant_labels):
            if not click_exact_text(
                frame,
                label,
                scope_texts=scope_texts,
                action_texts=scope_action_texts,
            ):
                manifest["actions"].append(
                    {
                        "key": f"variant_{index + 1}",
                        "label": f"切换视图失败：{label}",
                        "captured_at": now_local().isoformat(),
                        "status": "missing_variant",
                        "request_count": 0,
                        "response_count": 0,
                        "request_diffs": [],
                        "response_fingerprints": [],
                    }
                )
                continue
            run_action(
                f"variant_{index + 1}",
                f"切换视图：{label}",
                lambda label=label: click_exact_text(
                    frame,
                    label,
                    scope_texts=scope_texts,
                    action_texts=scope_action_texts,
                ),
                wait_ms=1800,
            )
            if entry.recipe.query_required:
                run_action(
                    f"variant_{index + 1}_query",
                    f"切换后查询：{label}",
                    lambda: click_query_button(
                        frame,
                        scope_texts=scope_texts,
                        action_texts=scope_action_texts,
                    ),
                    wait_ms=2500,
                )

        if probe_target and entry.title in set(get_probe_target_titles(probe_target)):
            for probe_case in build_single_variable_probe_cases(entry):
                reference_payloads = None
                if probe_case.reference_payload is not None:
                    reference_payloads = {
                        extract_endpoint_name(probe_case.url): probe_case.reference_payload,
                    }
                run_action(
                    probe_case.key,
                    probe_case.label,
                    lambda probe_case=probe_case: perform_authenticated_probe_fetch(
                        page,
                        url=probe_case.url,
                        payload=probe_case.payload,
                    ),
                    wait_ms=2200,
                    metadata={
                        "probe": {
                            "parameter_path": probe_case.parameter_path,
                            "parameter_value": probe_case.parameter_value,
                            "category": probe_case.category,
                            "notes": probe_case.notes,
                            "url": probe_case.url,
                        }
                    },
                    reference_payloads=reference_payloads,
                )
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = str(exc)

    manifest["network"] = {
        "requests": collector.requests,
        "responses": collector.responses,
    }
    manifest["summary"] = build_page_manifest_summary(manifest)
    safe_json_dump(page_dir / "manifest.json", manifest)
    collector.close()
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="通过 Playwright 研究 Yeusoft 页面动作与接口参数变化。")
    parser.add_argument("--site-url", default=SITE_URL, help="Yeusoft 站点地址")
    parser.add_argument("--report-doc", default=str(DEFAULT_REPORT_DOC), help="report_api_samples.md 路径")
    parser.add_argument("--api-images-dir", default=str(DEFAULT_API_IMAGES_DIR), help="API-images 目录")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="原始浏览器研究产物根目录")
    parser.add_argument("--analysis-root", default=str(DEFAULT_ANALYSIS_ROOT), help="结构化分析结果目录")
    parser.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR), help="Playwright 持久化 profile 目录")
    parser.add_argument("--start-date", default=DEFAULT_QUERY_DATE_RANGE["start"], help="研究用开始日期")
    parser.add_argument("--end-date", default=DEFAULT_QUERY_DATE_RANGE["end"], help="研究用结束日期")
    parser.add_argument("--only", action="append", default=[], help="只跑指定页面标题，可重复传")
    parser.add_argument("--limit", type=int, help="限制页面数量")
    parser.add_argument("--probe-target", choices=sorted(SECOND_ROUND_PROBE_TARGETS))
    parser.add_argument("--include-unknown-pages", action="store_true", help="把最新菜单覆盖审计里的 visible_but_untracked 页面并入研究")
    parser.add_argument("--unknown-pages-only", action="store_true", help="只跑最新菜单覆盖审计里的 visible_but_untracked 页面")
    parser.add_argument("--headless", action="store_true", help="使用 headless 运行")
    parser.add_argument("--skip-screenshots", action="store_true", help="跳过页面截图")
    parser.add_argument("--capture-all-network", action="store_true", help="记录所有 Yeusoft API 请求，仅用于定向页面研究")
    args = parser.parse_args()

    sync_playwright, _ = import_playwright()
    registry = build_page_research_registry(Path(args.report_doc), Path(args.api_images_dir))
    if args.include_unknown_pages or args.unknown_pages_only:
        _, menu_coverage_payload = load_latest_menu_coverage_audit(Path(args.analysis_root))
        unknown_entries = build_unknown_page_registry_entries(
            menu_coverage_payload,
            existing_registry=registry,
        )
        if args.unknown_pages_only:
            registry = unknown_entries
        else:
            registry = [*registry, *unknown_entries]
    if args.probe_target:
        target_titles = set(get_probe_target_titles(args.probe_target))
        registry = [entry for entry in registry if entry.title in target_titles]
    if args.only:
        wanted = {title.strip() for title in args.only if title.strip()}
        missing_titles = {
            title
            for title in wanted
            if not any(
                title in {entry.title, entry.canonical_name, entry.menu_target_title}
                for entry in registry
            )
        }
        if missing_titles:
            _, menu_coverage_payload = load_latest_menu_coverage_audit(Path(args.analysis_root))
            if menu_coverage_payload:
                registry = [
                    *registry,
                    *build_menu_coverage_registry_entries(
                        menu_coverage_payload,
                        existing_registry=registry,
                        only_titles=sorted(missing_titles),
                    ),
                ]
        registry = [
            entry
            for entry in registry
            if entry.title in wanted
            or entry.canonical_name in wanted
            or entry.menu_target_title in wanted
        ]
    if args.limit is not None:
        registry = registry[: args.limit]

    run_dir = Path(args.output_root) / now_local().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(Path(args.profile_dir)),
            headless=args.headless,
            viewport={"width": 1440, "height": 1200},
        )
        try:
            page = context.new_page()
            page.goto(args.site_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2500)
            auth = ensure_login_ready(page, interactive=not args.headless)
            bootstrap_state = bootstrap_operational_route(page)
            shell_state = wait_for_operational_shell(page)
            page.wait_for_timeout(2000)
            frame = wait_for_operational_frame(page)
            menu_list = fetch_menu_list(page)
            manifests = []
            menu_lookup = build_menu_lookup(menu_list)
            for entry in registry:
                print(f"[research] {entry.title}")
                entry_start_date, entry_end_date = resolve_entry_date_range(
                    entry,
                    default_start=args.start_date,
                    default_end=args.end_date,
                    analysis_root=Path(args.analysis_root),
                )
                manifests.append(
                    research_single_page(
                        entry=entry,
                        page=page,
                        frame=frame,
                        menu_lookup=menu_lookup,
                        run_dir=run_dir,
                        start_date=entry_start_date,
                        end_date=entry_end_date,
                        skip_screenshots=args.skip_screenshots,
                        probe_target=args.probe_target,
                        capture_all_network=args.capture_all_network,
                    )
                )
            run_index = {
                "generated_at": now_local().isoformat(),
                "site_url": args.site_url,
                "auth_context": auth,
                "bootstrap_state": bootstrap_state,
                "shell_state": shell_state,
                "probe_target": args.probe_target,
                "registry_size": len(registry),
                "menu_items": list_menu_items(menu_list),
                "report_menu_items": list_report_menu_items(menu_list),
                "summary": summarize_page_manifests(manifests),
            }
            safe_json_dump(run_dir / "index.json", run_index)
            analysis_output = Path(args.analysis_root) / f"yeusoft-page-research-{run_dir.name}.json"
            safe_json_dump(analysis_output, run_index["summary"])
            print(json.dumps({"ok": True, "run_dir": str(run_dir), "analysis": str(analysis_output)}, ensure_ascii=False))
        finally:
            context.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
