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

from app.services.research.menu_coverage import load_latest_menu_coverage_audit
from app.services.research.page_research import (
    ResearchPageRegistryEntry,
    build_menu_coverage_registry_entries,
    build_page_research_registry,
    build_page_scope_action_texts,
    build_page_scope_texts,
)
from scripts.run_yeusoft_page_research import (
    DEFAULT_API_IMAGES_DIR,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_PROFILE_DIR,
    DEFAULT_REPORT_DOC,
    NETWORK_WAIT_MS,
    NetworkCollector,
    bootstrap_operational_route,
    build_menu_lookup,
    build_step_delta,
    capture_component_state,
    capture_step_ui_state,
    capture_visible_controls,
    click_exact_text,
    click_query_button,
    ensure_login_ready,
    fetch_menu_list,
    import_playwright,
    lookup_menu_item,
    now_local,
    open_report_by_menu_item,
    resolve_page_scope,
    safe_json_dump,
    select_first_grid_row,
    wait_for_operational_frame,
    wait_for_operational_shell,
)


ACTION_BUTTONS: tuple[str, ...] = ("查看明细", "条码记录", "统计损溢", "新增")
SAFE_COMPONENT_METHODS: tuple[str, ...] = ("getDataList", "getDetailList", "getDiffData", "barcodeRecard", "statisticalClick")
COMPONENT_NAME = "inventoryTable"
SELECTION_FIELD_CANDIDATES: tuple[str, ...] = ("selectItem", "currentRow", "firstSelectItem", "secondSelectItem")
FULL_ROW_EXPORT_KEYS = {
    "orderDetailData",
    "orderDiffData",
    "orderHJData",
    "orderDetailHJData",
    "orderDiffHJData",
}


def _capture_nested_row_context(frame, *, component_name: str) -> dict[str, Any]:
    return frame.evaluate(
        """(componentName) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          const all = nodes.filter((node) => node.__vue__).map((node) => node.__vue__);
          const nested = all.find((candidate) => {
            if (candidate === vm) return false;
            const tableData = candidate?.vxeTable?.tableData || candidate?.tableData || null;
            return Array.isArray(tableData) && tableData.length > 0;
          }) || null;
          const tableData = nested?.vxeTable?.tableData || nested?.tableData || [];
          const firstRow = Array.isArray(tableData) && tableData.length ? tableData[0] : null;
          const rowState = {};
          if (vm) {
            for (const key of Object.keys(vm)) {
              if (key.startsWith('_')) continue;
              if (!/(select|row|item|current|detail|diff|order|pd)/i.test(key)) continue;
              const value = vm[key];
              if (value === null || value === undefined) {
                rowState[key] = null;
              } else if (Array.isArray(value)) {
                rowState[key] = { type: 'array', length: value.length };
              } else if (typeof value === 'object') {
                rowState[key] = { type: 'object', keys: Object.keys(value).slice(0, 12) };
              } else {
                rowState[key] = value;
              }
            }
          }
          return {
            component_found: !!vm,
            nested_component_found: !!nested,
            nested_component_name: nested?.$options?.name || nested?.$options?._componentTag || null,
            table_length: Array.isArray(tableData) ? tableData.length : 0,
            first_row: firstRow,
            first_row_keys: firstRow && typeof firstRow === 'object' ? Object.keys(firstRow).slice(0, 24) : [],
            root_row_state: rowState,
          };
        }""",
        component_name,
    )


def _capture_local_detail_state(frame, *, component_name: str) -> dict[str, Any]:
    return frame.evaluate(
        """([componentName, fullRowExportKeys]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          if (!vm) {
            return {"component_found": false};
          }

          const summarizeValue = (value) => {
            if (value === null || value === undefined) return null;
            if (Array.isArray(value)) {
              const sample = value[0];
              return {
                type: 'array',
                length: value.length,
                sample_keys: sample && typeof sample === 'object' && !Array.isArray(sample)
                  ? Object.keys(sample).slice(0, 16)
                  : [],
                sample_rows: value.slice(0, 2),
              };
            }
            if (typeof value === 'object') {
              return {
                type: 'object',
                keys: Object.keys(value).slice(0, 16),
              };
            }
            return value;
          };

          const focusKeys = [
            'showDetailPage',
            'showDiffPage',
            'showBarcodePage',
            'detailVisible',
            'diffVisible',
            'barcodeVisible',
            'orderDetailData',
            'orderDiffData',
            'orderHJData',
            'orderDetailHJData',
            'orderDiffHJData',
            'barcodeData',
            'tableData',
            'detailTableData',
            'diffTableData',
            'selectItem',
            'currentRow',
            'firstSelectItem',
            'secondSelectItem',
          ];

          const snapshot = {};
          for (const key of focusKeys) {
            if (!(key in vm)) continue;
            snapshot[key] = summarizeValue(vm[key]);
            if (
              Array.isArray(vm[key]) &&
              vm[key].length > 0 &&
              Array.isArray(fullRowExportKeys) &&
              fullRowExportKeys.includes(key) &&
              vm[key].length <= 200
            ) {
              snapshot[key].full_rows = vm[key];
            }
          }

          const nestedComponents = nodes
            .filter((node) => node.__vue__ && node.__vue__ !== vm)
            .map((node) => node.__vue__)
            .filter((candidate) => {
              const name = candidate?.$options?.name || candidate?.$options?._componentTag || '';
              return /(reportTable|barcode|diff|detail)/i.test(String(name));
            })
            .slice(0, 8)
            .map((candidate) => {
              const name = candidate?.$options?.name || candidate?.$options?._componentTag || 'anonymous';
              const tableData = candidate?.vxeTable?.tableData || candidate?.tableData || null;
              return {
                name,
                tableData: summarizeValue(tableData),
              };
            });

          return {
            component_found: true,
            component_name: vm.$options?.name || vm.$options?._componentTag || componentName,
            snapshot,
            nested_components: nestedComponents,
          };
        }""",
        [component_name, list(FULL_ROW_EXPORT_KEYS)],
    )


def _resolve_page_entry(
    title: str,
    analysis_root: Path,
    *,
    report_doc: Path | None = None,
    api_images_dir: Path | None = None,
) -> ResearchPageRegistryEntry:
    registry = build_page_research_registry(
        Path(report_doc or DEFAULT_REPORT_DOC),
        Path(api_images_dir or DEFAULT_API_IMAGES_DIR),
    )
    entry = next((item for item in registry if item.title == title), None)
    if entry is not None:
        return entry

    _, menu_coverage_payload = load_latest_menu_coverage_audit(analysis_root)
    coverage_entries = build_menu_coverage_registry_entries(
        menu_coverage_payload,
        existing_registry=registry,
        only_titles=[title],
    )
    if coverage_entries:
        return coverage_entries[0]
    raise RuntimeError(f"未找到页面定义: {title}")


def _run_probe_action(
    *,
    page,
    frame,
    collector: NetworkCollector,
    action_key: str,
    callback,
    wait_ms: int,
    previous_requests: list[dict[str, Any]],
    scope_texts: tuple[str, ...],
    scope_action_texts: tuple[str, ...],
    metadata: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    collector.set_action(action_key)
    counts = collector.snapshot_counts()
    triggered = bool(callback())
    page.wait_for_timeout(wait_ms)
    delta = collector.collect_since(counts)
    step = {
        "key": action_key,
        "step": action_key,
        "captured_at": now_local().isoformat(),
        "action_triggered": triggered,
        **build_step_delta(delta, previous_requests),
        "ui_state": capture_step_ui_state(
            frame,
            scope_texts=scope_texts,
            action_texts=scope_action_texts,
        ),
        "component_state": capture_component_state(
            frame,
            scope_texts=scope_texts,
            action_texts=scope_action_texts,
        ),
    }
    if metadata:
        step.update(metadata)
    return step, previous_requests + delta.get("requests", [])


def _run_component_method_probe(
    *,
    page,
    frame,
    collector: NetworkCollector,
    component_name: str,
    method_name: str,
    wait_ms: int,
    previous_requests: list[dict[str, Any]],
    scope_texts: tuple[str, ...],
    scope_action_texts: tuple[str, ...],
    call_mode: str = "none",
    seed_selection_fields: tuple[str, ...] = (),
    row_index: int = 0,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    collector.set_action(f"component_method_{method_name}")
    counts = collector.snapshot_counts()
    nested_row_context_before = _capture_nested_row_context(frame, component_name=component_name)
    invocation = frame.evaluate(
        """async ([componentName, methodName, callMode, seedSelectionFields, rowIndex]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          if (!vm) {
            return { component_found: false, method_found: false, invoked: false };
          }
          const all = nodes.filter((node) => node.__vue__).map((node) => node.__vue__);
          const nested = all.find((candidate) => {
            if (candidate === vm) return false;
            const tableData = candidate?.vxeTable?.tableData || candidate?.tableData || null;
            return Array.isArray(tableData) && tableData.length > 0;
          }) || null;
          const tableData = nested?.vxeTable?.tableData || nested?.tableData || [];
          const selectedIndex = Array.isArray(tableData) && tableData.length ? Math.min(Math.max(Number(rowIndex) || 0, 0), tableData.length - 1) : 0;
          const selectedRow = Array.isArray(tableData) && tableData.length ? tableData[selectedIndex] : null;
          if (selectedRow && Array.isArray(seedSelectionFields)) {
            for (const field of seedSelectionFields) {
              if (!(field in vm)) continue;
              const value = vm[field];
              if (Array.isArray(value)) {
                vm[field] = value.length ? value : [selectedRow];
              } else if (value == null || value === '' || (typeof value === 'object' && !Object.keys(value).length)) {
                vm[field] = selectedRow;
              }
            }
          }
          const method = vm[methodName];
          if (typeof method !== 'function') {
            return { component_found: true, method_found: false, invoked: false, selected_row: selectedRow, row_index: selectedIndex };
          }
          try {
            let result;
            if (callMode === 'row') {
              result = method.call(vm, selectedRow);
            } else if (callMode === 'row_list') {
              result = method.call(vm, selectedRow ? [selectedRow] : []);
            } else {
              result = method.call(vm);
            }
            if (result && typeof result.then === 'function') {
              await result;
            }
            return {
              component_found: true,
              method_found: true,
              invoked: true,
              selected_row: selectedRow,
              row_index: selectedIndex,
              call_mode: callMode,
            };
          } catch (error) {
            return {
              component_found: true,
              method_found: true,
              invoked: false,
              selected_row: selectedRow,
              row_index: selectedIndex,
              call_mode: callMode,
              error: String(error),
            };
          }
        }""",
        [component_name, method_name, call_mode, list(seed_selection_fields), row_index],
    )
    page.wait_for_timeout(wait_ms)
    delta = collector.collect_since(counts)
    step = {
        "key": f"component_method_{method_name}",
        "step": f"component_method_{method_name}",
        "captured_at": now_local().isoformat(),
        "action_triggered": bool(invocation.get("invoked")),
        "component_invocation": invocation,
        "row_index": row_index,
        "nested_row_context_before": nested_row_context_before,
        "local_state_before": _capture_local_detail_state(frame, component_name=component_name),
        **build_step_delta(delta, previous_requests),
        "ui_state": capture_step_ui_state(
            frame,
            scope_texts=scope_texts,
            action_texts=scope_action_texts,
        ),
        "component_state": capture_component_state(
            frame,
            scope_texts=scope_texts,
            action_texts=scope_action_texts,
        ),
        "nested_row_context_after": _capture_nested_row_context(frame, component_name=component_name),
        "local_state_after": _capture_local_detail_state(frame, component_name=component_name),
    }
    return step, previous_requests + delta.get("requests", [])


def main() -> int:
    parser = argparse.ArgumentParser(description="对 Yeusoft 门店盘点单页面做 UI 动作链取证，抓取主列表与二级按钮后的真实请求变化")
    parser.add_argument("--site-url", default="https://jypos.yeusoft.net/")
    parser.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--analysis-root", default=str(PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--wait-ms", type=int, default=NETWORK_WAIT_MS)
    parser.add_argument("--query-wait-ms", type=int, default=20000)
    args = parser.parse_args()

    entry = _resolve_page_entry("门店盘点单", Path(args.analysis_root))
    sync_playwright, _ = import_playwright()

    run_dir = Path(args.output_root) / f"{now_local().strftime('%Y%m%d-%H%M%S')}-store-stocktaking-ui-probe"
    page_dir = run_dir / entry.slug
    page_dir.mkdir(parents=True, exist_ok=True)

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
            menu_lookup = build_menu_lookup(fetch_menu_list(page))
            menu_item = lookup_menu_item(menu_lookup, entry)
            if menu_item is None:
                raise RuntimeError("未在菜单树中找到门店盘点单")

            collector = NetworkCollector(page, page_dir, capture_all_network=True)
            try:
                scope_texts = build_page_scope_texts(entry)
                scope_action_texts = build_page_scope_action_texts(entry)
                previous_requests: list[dict[str, Any]] = []
                result: dict[str, Any] = {
                    "generated_at": now_local().isoformat(),
                    "page": entry.as_dict(),
                    "auth_context": auth,
                    "bootstrap_state": bootstrap_state,
                    "shell_state": shell_state,
                    "baseline": {},
                    "action_probes": [],
                    "component_method_probes": [],
                }

                open_step, previous_requests = _run_probe_action(
                    page=page,
                    frame=frame,
                    collector=collector,
                    action_key="open_store_stocktaking",
                    callback=lambda: bool(open_report_by_menu_item(frame, page, menu_item) or True),
                    wait_ms=args.wait_ms,
                    previous_requests=previous_requests,
                    scope_texts=scope_texts,
                    scope_action_texts=scope_action_texts,
                )
                result["baseline"]["open_step"] = open_step
                result["baseline"]["page_scope_after_open"] = resolve_page_scope(
                    frame,
                    scope_texts=scope_texts,
                    action_texts=scope_action_texts,
                )
                result["baseline"]["component_state_after_open"] = capture_component_state(
                    frame,
                    scope_texts=scope_texts,
                    action_texts=scope_action_texts,
                )
                result["baseline"]["visible_controls_after_open"] = capture_visible_controls(
                    frame,
                    scope_texts=scope_texts,
                    action_texts=scope_action_texts,
                )

                query_step, previous_requests = _run_probe_action(
                    page=page,
                    frame=frame,
                    collector=collector,
                    action_key="baseline_query",
                    callback=lambda: click_query_button(
                        frame,
                        scope_texts=scope_texts,
                        action_texts=scope_action_texts,
                    ),
                    wait_ms=args.query_wait_ms,
                    previous_requests=previous_requests,
                    scope_texts=scope_texts,
                    scope_action_texts=scope_action_texts,
                )
                result["baseline"]["query_step"] = query_step
                result["baseline"]["component_state_after_query"] = capture_component_state(
                    frame,
                    scope_texts=scope_texts,
                    action_texts=scope_action_texts,
                )
                result["baseline"]["local_state_after_query"] = _capture_local_detail_state(
                    frame,
                    component_name=COMPONENT_NAME,
                )
                result["baseline"]["nested_row_context_after_query"] = _capture_nested_row_context(
                    frame,
                    component_name=COMPONENT_NAME,
                )
                result["baseline"]["visible_controls_after_query"] = capture_visible_controls(
                    frame,
                    scope_texts=scope_texts,
                    action_texts=scope_action_texts,
                )

                for label in ACTION_BUTTONS:
                    select_step, previous_requests = _run_probe_action(
                        page=page,
                        frame=frame,
                        collector=collector,
                        action_key=f"select_row_before_{label}",
                        callback=lambda: select_first_grid_row(
                            frame,
                            scope_texts=scope_texts,
                            action_texts=scope_action_texts,
                        ),
                        wait_ms=1200,
                        previous_requests=previous_requests,
                        scope_texts=scope_texts,
                        scope_action_texts=scope_action_texts,
                        metadata={"button_label": label},
                    )
                    click_step, previous_requests = _run_probe_action(
                        page=page,
                        frame=frame,
                        collector=collector,
                        action_key=f"click_{label}",
                        callback=lambda label=label: click_exact_text(
                            frame,
                            label,
                            scope_texts=scope_texts,
                            action_texts=scope_action_texts,
                        ),
                        wait_ms=2200,
                        previous_requests=previous_requests,
                        scope_texts=scope_texts,
                        scope_action_texts=scope_action_texts,
                        metadata={"button_label": label},
                    )
                    result["action_probes"].append(
                        {
                            "button_label": label,
                            "select_step": select_step,
                            "click_step": click_step,
                        }
                    )

                for method_name in SAFE_COMPONENT_METHODS:
                    method_step, previous_requests = _run_component_method_probe(
                        page=page,
                        frame=frame,
                        collector=collector,
                        component_name=COMPONENT_NAME,
                        method_name=method_name,
                        wait_ms=2500,
                        previous_requests=previous_requests,
                        scope_texts=scope_texts,
                        scope_action_texts=scope_action_texts,
                    )
                    result["component_method_probes"].append(method_step)
                    if method_name == "getDiffData":
                        for row_index in (1, 2):
                            row_step, previous_requests = _run_component_method_probe(
                                page=page,
                                frame=frame,
                                collector=collector,
                                component_name=COMPONENT_NAME,
                                method_name="getDiffData",
                                wait_ms=2500,
                                previous_requests=previous_requests,
                                scope_texts=scope_texts,
                                scope_action_texts=scope_action_texts,
                                call_mode="row",
                                seed_selection_fields=SELECTION_FIELD_CANDIDATES,
                                row_index=row_index,
                            )
                            row_step["key"] = f"component_method_getDiffData_row_{row_index}"
                            row_step["step"] = f"component_method_getDiffData_row_{row_index}"
                            result["component_method_probes"].append(row_step)

                component_selection_steps = (
                    ("getDetailList", "row"),
                    ("getDiffData", "row"),
                    ("barcodeRecard", "row"),
                    ("statisticalClick", "row"),
                )
                for method_name, call_mode in component_selection_steps:
                    method_step, previous_requests = _run_component_method_probe(
                        page=page,
                        frame=frame,
                        collector=collector,
                        component_name=COMPONENT_NAME,
                        method_name=method_name,
                        wait_ms=2500,
                        previous_requests=previous_requests,
                        scope_texts=scope_texts,
                        scope_action_texts=scope_action_texts,
                        call_mode=call_mode,
                        seed_selection_fields=SELECTION_FIELD_CANDIDATES,
                    )
                    result["component_method_probes"].append(method_step)

                safe_json_dump(page_dir / "manifest.json", result)
                analysis_path = Path(args.analysis_root) / f"store-stocktaking-ui-probe-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
                safe_json_dump(analysis_path, result)
                print(json.dumps({"ok": True, "output": str(analysis_path)}, ensure_ascii=False))
            finally:
                collector.close()
        finally:
            context.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
