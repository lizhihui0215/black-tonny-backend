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
from app.services.menu_coverage_audit_service import load_latest_menu_coverage_audit
from app.services.yeusoft_page_research_service import (
    DEFAULT_QUERY_DATE_RANGE,
    INTERACTIVE_TEXT_SELECTOR,
    SECOND_ROUND_PROBE_TARGETS,
    build_menu_lookup,
    build_unknown_page_registry_entries,
    build_page_manifest_summary,
    build_single_variable_probe_cases,
    build_page_research_registry,
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


def now_local() -> datetime:
    return datetime.now(LOCAL_TZ)


def safe_json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")


def sanitize_filename(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value).strip("_")[:80] or "artifact"


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


def click_exact_text(frame, text: str) -> bool:
    return bool(
        frame.evaluate(
            """([selector, expectedText]) => {
              const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
              const candidates = Array.from(document.querySelectorAll(selector))
                .filter((item) => {
                  const rect = item.getBoundingClientRect();
                  return rect.width > 0 && rect.height > 0 && normalize(item.textContent) === expectedText;
                })
                .sort((left, right) => normalize(left.textContent).length - normalize(right.textContent).length);
              const target = candidates[0];
              if (!target) return false;
              target.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
              return true;
            }""",
            [INTERACTIVE_TEXT_SELECTOR, text],
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


def capture_visible_controls(frame) -> list[dict[str, Any]]:
    return frame.evaluate(
        """(selector) => {
          const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
          return Array.from(document.querySelectorAll(selector))
            .filter((item) => {
              const rect = item.getBoundingClientRect();
              return rect.width > 0 && rect.height > 0;
            })
            .map((item) => ({
              tag: item.tagName.toLowerCase(),
              text: normalize(item.textContent),
              className: item.className || '',
            }))
            .filter((item) => item.text)
            .slice(0, 200);
        }""",
        INTERACTIVE_TEXT_SELECTOR,
    )


def try_set_date_range(frame, start_date: str, end_date: str) -> bool:
    return bool(
        frame.evaluate(
            """([startDate, endDate]) => {
              const selectors = [
                '.el-date-editor input',
                '.el-range-editor input',
                "input[placeholder*='开始']",
                "input[placeholder*='结束']",
                "input[placeholder*='时间']",
              ];
              const inputs = Array.from(document.querySelectorAll(selectors.join(',')))
                .filter((input) => {
                  const rect = input.getBoundingClientRect();
                  return rect.width > 0 && rect.height > 0;
                });
              if (inputs.length < 2) return false;
              inputs[0].value = '';
              inputs[0].dispatchEvent(new Event('input', { bubbles: true }));
              inputs[0].value = startDate;
              inputs[0].dispatchEvent(new Event('input', { bubbles: true }));
              inputs[0].dispatchEvent(new Event('change', { bubbles: true }));
              inputs[1].value = '';
              inputs[1].dispatchEvent(new Event('input', { bubbles: true }));
              inputs[1].value = endDate;
              inputs[1].dispatchEvent(new Event('input', { bubbles: true }));
              inputs[1].dispatchEvent(new Event('change', { bubbles: true }));
              inputs[1].dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
              return true;
            }""",
            [start_date, end_date],
        )
    )


def click_query_button(frame) -> bool:
    return bool(
        frame.evaluate(
            """() => {
              const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
              const candidates = Array.from(document.querySelectorAll('button, .el-button'))
                .filter((item) => {
                  const rect = item.getBoundingClientRect();
                  return rect.width > 0 && rect.height > 0;
                });
              const target = candidates.find((item) => normalize(item.textContent) === '查询')
                || candidates.find((item) => normalize(item.textContent).includes('查询'));
              if (!target) return false;
              target.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
              return true;
            }"""
        )
    )


class NetworkCollector:
    def __init__(self, page, page_dir: Path):
        self.page = page
        self.page_dir = page_dir
        self.network_dir = page_dir / "network"
        self.network_dir.mkdir(parents=True, exist_ok=True)
        self.requests: list[dict[str, Any]] = []
        self.responses: list[dict[str, Any]] = []
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
        if not is_interesting_endpoint(url):
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
        if not is_interesting_endpoint(url):
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
        response_summary = analyze_response_payload(body) if suffix == "json" else None
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
) -> dict[str, Any]:
    page_dir = run_dir / entry.slug
    page_dir.mkdir(parents=True, exist_ok=True)
    collector = NetworkCollector(page, page_dir)
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
        callback()
        page.wait_for_timeout(wait_ms)
        delta = collector.collect_since(counts)
        step = {
            "key": action_key,
            "label": label,
            "captured_at": now_local().isoformat(),
            **build_step_delta(delta, previous_requests, reference_payloads=reference_payloads),
        }
        if metadata:
            step.update(metadata)
        manifest["actions"].append(step)
        previous_requests = previous_requests + delta["requests"]

    try:
        menu_item = lookup_menu_item(menu_lookup, entry)
        if not menu_item:
            raise RuntimeError(f"菜单中未找到页面：{entry.title}")

        run_action("open", "打开页面", lambda: open_report_by_menu_item(frame, page, menu_item))
        if not skip_screenshots:
            page.screenshot(path=str(page_dir / "opened.png"), full_page=True)
        manifest["visible_controls"] = capture_visible_controls(frame)

        if entry.recipe.date_range_applicable:
            run_action(
                "set_date_range",
                "设置日期范围",
                lambda: try_set_date_range(frame, start_date, end_date),
                wait_ms=1200,
            )

        if entry.recipe.query_required:
            run_action("query", "执行查询", lambda: click_query_button(frame))
            if not skip_screenshots:
                page.screenshot(path=str(page_dir / "queried.png"), full_page=True)

        for index, label in enumerate(entry.recipe.variant_labels):
            if not click_exact_text(frame, label):
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
                lambda label=label: click_exact_text(frame, label),
                wait_ms=1800,
            )
            if entry.recipe.query_required:
                run_action(
                    f"variant_{index + 1}_query",
                    f"切换后查询：{label}",
                    lambda: click_query_button(frame),
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
            pages = read_member(context, "pages", [])
            page = pages[0] if pages else context.new_page()
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
                manifests.append(
                    research_single_page(
                        entry=entry,
                        page=page,
                        frame=frame,
                        menu_lookup=menu_lookup,
                        run_dir=run_dir,
                        start_date=args.start_date,
                        end_date=args.end_date,
                        skip_screenshots=args.skip_screenshots,
                        probe_target=args.probe_target,
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
