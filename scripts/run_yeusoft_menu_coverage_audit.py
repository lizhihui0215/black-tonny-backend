#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.menu_coverage_audit_service import build_menu_coverage_audit
from app.services.yeusoft_page_research_service import (
    DEFAULT_QUERY_DATE_RANGE,
    build_page_research_registry,
    load_page_research_manifests,
)
from scripts.run_yeusoft_page_research import (
    DEFAULT_ANALYSIS_ROOT,
    DEFAULT_API_IMAGES_DIR,
    DEFAULT_PROFILE_DIR,
    DEFAULT_REPORT_DOC,
    NETWORK_WAIT_MS,
    SITE_URL,
    NetworkCollector,
    bootstrap_operational_route,
    build_step_delta,
    capture_visible_controls,
    click_query_button,
    ensure_login_ready,
    fetch_menu_list,
    import_playwright,
    list_menu_items,
    now_local,
    open_report_by_menu_item,
    read_member,
    safe_json_dump,
    try_set_date_range,
    wait_for_operational_frame,
    wait_for_operational_shell,
)


DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "output" / "playwright" / "yeusoft-menu-coverage"


def sanitize_filename(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value).strip("_")[:120] or "artifact"


def _page_dir_name(menu_item: dict[str, Any]) -> str:
    parts = [
        str(menu_item.get("rootName") or "").strip(),
        str(menu_item.get("groupName") or "").strip(),
        str(menu_item.get("FuncName") or "").strip(),
    ]
    joined = "__".join(part for part in parts if part)
    return sanitize_filename(joined)


def _collect_candidate_endpoints(requests: list[dict[str, Any]], responses: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    endpoints = []
    data_endpoints = []
    response_by_request_id = {item.get("request_id"): item for item in responses if item.get("request_id") is not None}
    for request in requests:
        url = str(request.get("url") or "")
        endpoint = url.rstrip("/").split("/")[-1]
        if not endpoint:
            continue
        endpoints.append(endpoint)
        response = response_by_request_id.get(request.get("id"))
        summary = (response or {}).get("response_summary") or {}
        if summary.get("row_count") is not None:
            data_endpoints.append(endpoint)
    return list(dict.fromkeys(endpoints)), list(dict.fromkeys(data_endpoints))


def _supports_date_range(frame) -> bool:
    return bool(
        frame.evaluate(
            """() => {
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
              return inputs.length >= 2;
            }"""
        )
    )


def _supports_query_button(frame) -> bool:
    return bool(
        frame.evaluate(
            """() => {
              const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
              const candidates = Array.from(document.querySelectorAll('button, .el-button'))
                .filter((item) => {
                  const rect = item.getBoundingClientRect();
                  return rect.width > 0 && rect.height > 0;
                });
              return candidates.some((item) => normalize(item.textContent) === '查询' || normalize(item.textContent).includes('查询'));
            }"""
        )
    )


def audit_single_menu_page(
    *,
    page,
    frame,
    menu_item: dict[str, Any],
    run_dir: Path,
    start_date: str,
    end_date: str,
    skip_screenshots: bool,
) -> dict[str, Any]:
    page_dir = run_dir / "pages" / _page_dir_name(menu_item)
    page_dir.mkdir(parents=True, exist_ok=True)
    collector = NetworkCollector(page, page_dir)
    previous_requests: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {
        "generated_at": now_local().isoformat(),
        "menu_item": menu_item,
        "status": "opened",
        "actions": [],
        "visible_controls": [],
        "network": {"requests": [], "responses": []},
    }

    def run_action(action_key: str, label: str, callback, wait_ms: int = NETWORK_WAIT_MS) -> None:
        nonlocal previous_requests
        collector.set_action(action_key)
        counts = collector.snapshot_counts()
        callback()
        page.wait_for_timeout(wait_ms)
        delta = collector.collect_since(counts)
        manifest["actions"].append(
            {
                "key": action_key,
                "label": label,
                "captured_at": now_local().isoformat(),
                **build_step_delta(delta, previous_requests),
            }
        )
        previous_requests = previous_requests + delta["requests"]

    try:
        run_action("open", "打开页面", lambda: open_report_by_menu_item(frame, page, menu_item))
        manifest["visible_controls"] = capture_visible_controls(frame)
        if not skip_screenshots:
            page.screenshot(path=str(page_dir / "opened.png"), full_page=True)

        if _supports_date_range(frame):
            run_action("set_date_range", "设置统一日期范围", lambda: try_set_date_range(frame, start_date, end_date), wait_ms=1200)

        if _supports_query_button(frame):
            run_action("query", "执行查询", lambda: click_query_button(frame), wait_ms=2600)
            if not skip_screenshots:
                page.screenshot(path=str(page_dir / "queried.png"), full_page=True)
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = str(exc)

    manifest["network"] = {
        "requests": collector.requests,
        "responses": collector.responses,
    }
    candidate_endpoints, candidate_data_endpoints = _collect_candidate_endpoints(
        collector.requests,
        collector.responses,
    )
    manifest["candidate_endpoints"] = candidate_endpoints
    manifest["candidate_data_endpoints"] = candidate_data_endpoints
    safe_json_dump(page_dir / "manifest.json", manifest)
    collector.close()
    return {
        "title": str(menu_item.get("FuncName") or "").strip(),
        "menu_path": list(menu_item.get("menuPath") or []),
        "route_or_url": str(menu_item.get("FuncUrl") or ""),
        "open_status": "opened" if manifest["status"] == "opened" else "failed",
        "error": manifest.get("error"),
        "candidate_endpoints": candidate_endpoints,
        "candidate_data_endpoints": candidate_data_endpoints,
        "visible_control_count": len(manifest["visible_controls"]),
        "manifest_path": str((page_dir / "manifest.json").relative_to(run_dir)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="审计当前账号可见 Yeusoft 菜单覆盖，并输出页面到路线的覆盖结果。")
    parser.add_argument("--site-url", default=SITE_URL, help="Yeusoft 站点地址")
    parser.add_argument("--report-doc", default=str(DEFAULT_REPORT_DOC), help="report_api_samples.md 路径")
    parser.add_argument("--api-images-dir", default=str(DEFAULT_API_IMAGES_DIR), help="API-images 目录")
    parser.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR), help="Playwright 持久化 profile 目录")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="原始浏览器审计产物根目录")
    parser.add_argument("--analysis-root", default=str(DEFAULT_ANALYSIS_ROOT), help="结构化 analysis 输出目录")
    parser.add_argument("--start-date", default=DEFAULT_QUERY_DATE_RANGE["start"], help="统一审计开始日期")
    parser.add_argument("--end-date", default=DEFAULT_QUERY_DATE_RANGE["end"], help="统一审计结束日期")
    parser.add_argument("--limit", type=int, help="限制审计页面数量")
    parser.add_argument("--headless", action="store_true", help="使用 headless 运行")
    parser.add_argument("--skip-screenshots", action="store_true", help="跳过页面截图")
    args = parser.parse_args()

    sync_playwright, _ = import_playwright()
    registry = build_page_research_registry(Path(args.report_doc), Path(args.api_images_dir))
    latest_page_research_dir = Path(args.output_root).parent / "yeusoft-research"
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
            safe_json_dump(run_dir / "menu-tree.json", menu_list)

            menu_items = list_menu_items(menu_list)
            if args.limit is not None:
                menu_items = menu_items[: args.limit]

            audited_pages = []
            for menu_item in menu_items:
                print(f"[coverage] {' / '.join(menu_item.get('menuPath') or [])}")
                audited_pages.append(
                    audit_single_menu_page(
                        page=page,
                        frame=frame,
                        menu_item=menu_item,
                        run_dir=run_dir,
                        start_date=args.start_date,
                        end_date=args.end_date,
                        skip_screenshots=args.skip_screenshots,
                    )
                )

            latest_page_research_pages = []
            if latest_page_research_dir.exists():
                run_dirs = sorted(path for path in latest_page_research_dir.iterdir() if path.is_dir())
                if run_dirs:
                    latest_page_research_pages = load_page_research_manifests(run_dirs[-1])

            audit = build_menu_coverage_audit(
                menu_list=menu_list,
                registry=registry,
                audited_pages=audited_pages,
                latest_page_research_pages=latest_page_research_pages,
            )
            output = {
                "generated_at": now_local().isoformat(),
                "site_url": args.site_url,
                "auth_context": auth,
                "bootstrap_state": bootstrap_state,
                "shell_state": shell_state,
                "summary": audit["summary"],
                "pages": audit["pages"],
                "containers": audit["containers"],
                "menu_tree_path": str((run_dir / "menu-tree.json").relative_to(run_dir)),
                "audited_page_manifests": audited_pages,
                "registry_size": len(registry),
                "latest_page_research_count": len(latest_page_research_pages),
            }
            safe_json_dump(run_dir / "coverage-audit.json", output)
            analysis_output = Path(args.analysis_root) / f"menu-coverage-audit-{run_dir.name}.json"
            safe_json_dump(analysis_output, output)
            print(json.dumps({"ok": True, "run_dir": str(run_dir), "analysis": str(analysis_output)}, ensure_ascii=False))
        finally:
            context.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
