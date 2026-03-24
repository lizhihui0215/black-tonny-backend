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


ACTION_BUTTONS: tuple[str, ...] = ("单据确认", "物流信息", "扫描校验")
SAFE_COMPONENT_METHODS: tuple[str, ...] = ("getDataList", "checkDetail", "getDetailData", "LogisticInfoClick")
COMPONENT_METHOD_SOURCE_NAMES: tuple[str, ...] = (
    "getDataList",
    "checkDetail",
    "getDetailData",
    "LogisticInfoClick",
    "tableSelectClick",
    "selectionChange",
)
COMPONENT_NAME = "receiveConfirm"
NESTED_TABLE_COMPONENT = "reportTable"
SELECTION_FIELD_CANDIDATES: tuple[str, ...] = ("selectItem", "currentRow", "currentItem")
COMPONENT_FIELD_PATTERN = r"(row|item|detail|order|doc|type|page|total|search|time|logistic|check|toggle|table|data|column|grid|load|view)"
REF_METHOD_PROBES: tuple[tuple[str, str], ...] = (
    ("reportTableItem_mainRef", "RTM_searchConditions"),
    ("reportTableItem_mainRef", "RTM_toggleCheckboxRow"),
    ("reportTableItem_mainRef", "RTM_GetViewGridHead"),
    ("reportTableItem_mainRef", "RTM_getTableHeader"),
    ("reportTableItem_mainRef", "finishLoadViewData"),
)
CHILD_REF_METHOD_PROBES: tuple[tuple[str, str, str], ...] = (
    ("reportTableItem_mainRef", "RTM_reportTable", "searchConditions"),
    ("reportTableItem_mainRef", "RTM_reportTable", "searchDataInfo"),
    ("reportTableItem_mainRef", "RTM_reportTable", "pageCondition"),
    ("reportTableItem_mainRef", "RTM_reportTable", "GetTotalData"),
    ("reportTableItem_mainRef", "RTM_reportTable", "allPageSelect"),
    ("reportTableItem_mainRef", "RTM_reportTable", "tableDataInit"),
    ("reportTableItem_mainRef", "RTM_reportTable", "finishViewData"),
    ("reportTableItem_mainRef", "RTM_reportTable", "vxeGirdLoadData"),
    ("reportTableItem_mainRef", "RTM_reportTable", "selectTableData"),
    ("reportTableItem_mainRef", "RTM_reportTable", "getTableHeaders"),
    ("reportTableItem_mainRef", "RTM_reportTable", "getTableDataCount"),
)
REF_METHOD_SOURCE_NAMES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("reportTableItem_mainRef", ("RTM_searchConditions", "RTM_toggleCheckboxRow", "RTM_getTableHeader", "finishLoadViewData")),
)
CHILD_REF_METHOD_SOURCE_NAMES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("reportTableItem_mainRef", "RTM_reportTable", ("searchDataInfo", "tableDataInit", "finishViewData", "vxeGirdLoadData", "getTableHeaders")),
)
ANCESTRY_METHOD_PATTERN = r"(receive|confirm|check|detail|order|table|grid|view|data|load|menu|search|page|select)"
ANCESTRY_REF_PROBES: tuple[tuple[int, str], ...] = (
    (1, "invoice01"),
    (1, "navmenu"),
)


def _capture_component_ancestry(
    frame,
    *,
    component_name: str,
    max_depth: int = 6,
) -> list[dict[str, Any]]:
    return frame.evaluate(
        """([componentName, maxDepth]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          if (!vm) return [];

          const summarizeValue = (value) => {
            if (value === null || value === undefined) return null;
            if (typeof value === 'function') return { type: 'function' };
            if (Array.isArray(value)) {
              const sample = value[0];
              return {
                type: 'array',
                length: value.length,
                sample_keys: sample && typeof sample === 'object' && !Array.isArray(sample)
                  ? Object.keys(sample).slice(0, 16)
                  : [],
              };
            }
            if (typeof value === 'object') {
              return {
                type: 'object',
                keys: Object.keys(value).slice(0, 20),
              };
            }
            return value;
          };

          const summarizeVm = (candidate, depth) => {
            const keys = Object.keys(candidate)
              .filter((key) => !key.startsWith('_') && !key.startsWith('$'))
              .slice(0, 200);
            const matchedKeys = keys
              .filter((key) => /(row|item|detail|order|doc|type|page|total|search|time|logistic|check|select|receive)/i.test(key))
              .slice(0, 40);
            const snapshot = Object.fromEntries(
              matchedKeys.map((key) => [key, summarizeValue(candidate[key])]),
            );
            const nestedSnapshots = {};
            for (const key of matchedKeys) {
              const value = candidate[key];
              if (!value || Array.isArray(value) || typeof value !== 'object') continue;
              const childKeys = Object.keys(value)
                .filter((childKey) => !childKey.startsWith('_') && !childKey.startsWith('$'))
                .slice(0, 20);
              nestedSnapshots[key] = Object.fromEntries(
                childKeys.map((childKey) => [childKey, summarizeValue(value[childKey])]),
              );
            }
            const nonEmptyCollections = [];
            for (const key of keys) {
              const value = candidate[key];
              if (!Array.isArray(value) || !value.length) continue;
              const sample = value[0];
              nonEmptyCollections.push({
                field: key,
                kind: sample && typeof sample === 'object' && !Array.isArray(sample) ? 'object_array' : 'scalar_array',
                length: value.length,
                sample_keys: sample && typeof sample === 'object' && !Array.isArray(sample)
                  ? Object.keys(sample).slice(0, 12)
                  : [],
              });
            }
            return {
              depth,
              component_name: candidate.$options?.name || candidate.$options?._componentTag || null,
              props_keys: candidate.$options?.props ? Object.keys(candidate.$options.props).slice(0, 20) : [],
              props_data_keys: candidate.$options?.propsData ? Object.keys(candidate.$options.propsData).slice(0, 20) : [],
              props_data_snapshot: candidate.$options?.propsData
                ? Object.fromEntries(
                    Object.entries(candidate.$options.propsData)
                      .slice(0, 20)
                      .map(([key, value]) => [key, summarizeValue(value)]),
                  )
                : {},
              refs: candidate.$refs ? Object.keys(candidate.$refs).slice(0, 20) : [],
              matched_keys: matchedKeys,
              snapshot,
              nested_snapshots: nestedSnapshots,
              non_empty_collections: nonEmptyCollections.slice(0, 12),
            };
          };

          const chain = [];
          let current = vm;
          let depth = 0;
          while (current && depth < maxDepth) {
            chain.push(summarizeVm(current, depth));
            current = current.$parent || null;
            depth += 1;
          }
          return chain;
        }""",
        [component_name, max_depth],
    )


def _capture_ancestry_ref_state(
    frame,
    *,
    component_name: str,
    depth: int,
    ref_name: str,
    field_pattern: str = COMPONENT_FIELD_PATTERN,
) -> dict[str, Any]:
    return frame.evaluate(
        """([componentName, depth, refName, pattern]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          const summarizeValue = (value) => {
            if (value === null || value === undefined) return null;
            if (typeof value === 'function') return { type: 'function' };
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
                keys: Object.keys(value).slice(0, 20),
              };
            }
            return value;
          };

          if (!vm) {
            return {
              component_found: false,
              ancestor_found: false,
              ref_found: false,
            };
          }

          let ancestor = vm;
          let remainingDepth = depth;
          while (ancestor && remainingDepth > 0) {
            ancestor = ancestor.$parent || null;
            remainingDepth -= 1;
          }

          if (!ancestor) {
            return {
              component_found: true,
              ancestor_found: false,
              ref_found: false,
              requested_depth: depth,
              ref_name: refName,
            };
          }

          const rawRef = ancestor.$refs?.[refName];
          const target = Array.isArray(rawRef) ? rawRef[0] : rawRef;
          if (!target || typeof target !== 'object') {
            return {
              component_found: true,
              ancestor_found: true,
              ref_found: false,
              requested_depth: depth,
              ref_name: refName,
              ancestor_component_name: ancestor.$options?.name || ancestor.$options?._componentTag || null,
              ancestor_ref_keys: ancestor.$refs ? Object.keys(ancestor.$refs).slice(0, 20) : [],
            };
          }

          const regex = new RegExp(pattern, 'i');
          const matchedKeys = Object.keys(target)
            .filter((key) => !key.startsWith('_') && !key.startsWith('$'))
            .filter((key) => regex.test(key))
            .slice(0, 40);
          const snapshot = Object.fromEntries(
            matchedKeys.map((key) => [key, summarizeValue(target[key])]),
          );

          const propsData = target.$options?.propsData || {};
          const propsDataSnapshot = Object.fromEntries(
            Object.entries(propsData)
              .slice(0, 20)
              .map(([key, value]) => [key, summarizeValue(value)]),
          );

          return {
            component_found: true,
            ancestor_found: true,
            ref_found: true,
            requested_depth: depth,
            ref_name: refName,
            ancestor_component_name: ancestor.$options?.name || ancestor.$options?._componentTag || null,
            component_name: target.$options?.name || target.$options?._componentTag || null,
            matched_keys: matchedKeys,
            snapshot,
            props_keys: target.$options?.props ? Object.keys(target.$options.props).slice(0, 20) : [],
            props_data_keys: Object.keys(propsData).slice(0, 20),
            props_data_snapshot: propsDataSnapshot,
            ref_keys: target.$refs ? Object.keys(target.$refs).slice(0, 20) : [],
          };
        }""",
        [component_name, depth, ref_name, field_pattern],
    )


def _capture_local_component_state(
    frame,
    *,
    component_name: str,
    nested_component_name: str | None = None,
) -> dict[str, Any]:
    return frame.evaluate(
        """([componentName, nestedComponentName]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          const summarizeValue = (value) => {
            if (value === null || value === undefined) return null;
            if (typeof value === 'function') return { type: 'function' };
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
                keys: Object.keys(value).slice(0, 20),
              };
            }
            return value;
          };
          const focusKeys = [
            'total',
            'page',
            'pageSize',
            'time',
            'search',
            'orderData',
            'orderDetailData',
            'orderHJData',
            'orderDetailHJData',
            'selectItem',
            'currentRow',
            'currentItem',
            'showDialog',
            'showLogisticDialog',
            'dialogVisible',
            'loading',
          ];
          const snapshot = {};
          if (vm) {
            for (const key of focusKeys) {
              if (!(key in vm)) continue;
              snapshot[key] = summarizeValue(vm[key]);
            }
          }
          const refsSnapshot = {};
          if (vm?.$refs) {
            for (const [refKey, refValue] of Object.entries(vm.$refs).slice(0, 20)) {
              const target = Array.isArray(refValue) ? refValue[0] : refValue;
              if (!target || typeof target !== 'object') continue;
              const ownKeys = Object.keys(target)
                .filter((key) => !key.startsWith('_') && !key.startsWith('$'))
                .filter((key) => /(row|item|detail|order|doc|type|page|total|search|time|logistic|check)/i.test(key))
                .slice(0, 30);
              const nestedSnapshots = {};
              for (const key of Object.keys(target).filter((key) => !key.startsWith('_') && !key.startsWith('$')).slice(0, 50)) {
                const value = target[key];
                if (!value || Array.isArray(value) || typeof value !== 'object') continue;
                const childKeys = Object.keys(value)
                  .filter((childKey) => !childKey.startsWith('_') && !childKey.startsWith('$'))
                  .filter((childKey) => /(row|item|detail|order|doc|type|page|total|search|time|logistic|check)/i.test(childKey))
                  .slice(0, 20);
                if (!childKeys.length) continue;
                const childSnapshot = {};
                for (const childKey of childKeys) {
                  childSnapshot[childKey] = summarizeValue(value[childKey]);
                }
                nestedSnapshots[key] = childSnapshot;
              }
              refsSnapshot[refKey] = {
                component_name: target.$options?.name || target.$options?._componentTag || null,
                matched_keys: ownKeys,
                snapshot: Object.fromEntries(ownKeys.map((key) => [key, summarizeValue(target[key])])),
                nested_snapshots: nestedSnapshots,
              };
            }
          }
          const all = nodes.filter((node) => node.__vue__).map((node) => node.__vue__);
          const nestedCandidates = all.filter((candidate) => candidate !== vm);
          const namedNested = nestedComponentName
            ? nestedCandidates.find((candidate) => (candidate.$options?.name || '') === nestedComponentName)
            : null;
          const dataNested = nestedCandidates.find((candidate) => {
            const tableData = candidate?.vxeTable?.tableData || candidate?.tableData || null;
            return Array.isArray(tableData) && tableData.length > 0;
          });
          const nested = namedNested || dataNested || null;
          const nestedTable = nested?.vxeTable?.tableData || nested?.tableData || [];
          return {
            component_found: !!vm,
            component_name: vm?.$options?.name || vm?.$options?._componentTag || componentName,
            snapshot,
            refs: vm?.$refs ? Object.keys(vm.$refs).slice(0, 30) : [],
            refs_snapshot: refsSnapshot,
            nested_component_name: nested?.$options?.name || nested?.$options?._componentTag || null,
            nested_table_length: Array.isArray(nestedTable) ? nestedTable.length : 0,
            nested_first_row: Array.isArray(nestedTable) && nestedTable.length ? nestedTable[0] : null,
          };
        }""",
        [component_name, nested_component_name],
    )


def _capture_ancestry_method_sources(
    frame,
    *,
    component_name: str,
    max_depth: int = 6,
    method_pattern: str = ANCESTRY_METHOD_PATTERN,
) -> list[dict[str, Any]]:
    return frame.evaluate(
        r"""([componentName, maxDepth, methodPattern]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          if (!vm) return [];

          const normalizeText = (value) => String(value).replace(/\s+/g, ' ').trim();
          const regex = new RegExp(methodPattern, 'i');
          const chain = [];
          let current = vm;
          let depth = 0;
          while (current && depth < maxDepth) {
            const ownKeys = Object.keys(current)
              .filter((key) => !key.startsWith('_') && !key.startsWith('$'))
              .slice(0, 400);
            const methodEntries = [];
            for (const key of ownKeys) {
              if (!regex.test(key)) continue;
              const value = current[key];
              if (typeof value !== 'function') continue;
              let source = '';
              try {
                source = String(value);
              } catch (error) {
                source = `__stringify_error__:${String(error)}`;
              }
              methodEntries.push({
                name: key,
                preview: normalizeText(source).slice(0, 300),
                length: source.length,
              });
            }
            chain.push({
              depth,
              component_name: current.$options?.name || current.$options?._componentTag || null,
              method_count: methodEntries.length,
              methods: methodEntries.slice(0, 24),
            });
            current = current.$parent || null;
            depth += 1;
          }
          return chain;
        }""",
        [component_name, max_depth, method_pattern],
    )


def _capture_component_store_state(frame, *, component_name: str) -> dict[str, Any]:
    return frame.evaluate(
        """(componentName) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          const summarizeValue = (value) => {
            if (value === null || value === undefined) return null;
            if (typeof value === 'function') return { type: 'function' };
            if (Array.isArray(value)) {
              const sample = value[0];
              return {
                type: 'array',
                length: value.length,
                sample_keys: sample && typeof sample === 'object' && !Array.isArray(sample)
                  ? Object.keys(sample).slice(0, 16)
                  : [],
              };
            }
            if (typeof value === 'object') {
              return {
                type: 'object',
                keys: Object.keys(value).slice(0, 20),
              };
            }
            return value;
          };
          const summarizeObjectByPattern = (target, pattern) => {
            if (!target || typeof target !== 'object') return {};
            const regex = new RegExp(pattern, 'i');
            const keys = Object.keys(target).filter((key) => regex.test(key)).slice(0, 40);
            return Object.fromEntries(keys.map((key) => [key, summarizeValue(target[key])]));
          };
          const store = vm?.$store || vm?.$root?.$store || null;
          const root = vm?.$root || null;
          const pattern = '(receive|confirm|check|doc|detail|order|table|menu|current|item|data|page|total)';
          return {
            component_found: !!vm,
            has_store: !!store,
            store_state_snapshot: summarizeObjectByPattern(store?.state, pattern),
            store_getter_keys: store?.getters ? Object.keys(store.getters).filter((key) => new RegExp(pattern, 'i').test(key)).slice(0, 40) : [],
            root_snapshot: summarizeObjectByPattern(root, pattern),
            root_data_snapshot: summarizeObjectByPattern(root?._data, pattern),
          };
        }""",
        component_name,
    )


def _capture_component_global_storage_state(frame, *, component_name: str) -> dict[str, Any]:
    return frame.evaluate(
        """(componentName) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          const pattern = /(receive|confirm|check|doc|detail|order|menu|item|current|table|grid|page|total|fxdatabase|e003001001|checkdoc)/i;

          const summarize = (value) => {
            if (value === null || value === undefined) return null;
            if (typeof value === 'function') return { type: 'function' };
            if (Array.isArray(value)) return { type: 'array', length: value.length };
            if (typeof value === 'object') return { type: 'object', keys: Object.keys(value).slice(0, 20) };
            return value;
          };

          const readStorage = (storage) => {
            const entries = [];
            if (!storage) return entries;
            for (let i = 0; i < storage.length; i += 1) {
              const key = storage.key(i);
              if (!key || !pattern.test(key)) continue;
              let raw = '';
              try {
                raw = storage.getItem(key) || '';
              } catch (error) {
                raw = `__read_error__:${String(error)}`;
              }
              let parsed = null;
              try {
                parsed = raw ? JSON.parse(raw) : null;
              } catch (error) {
                parsed = null;
              }
              entries.push({
                key,
                raw_preview: String(raw).slice(0, 300),
                parsed_summary: summarize(parsed),
              });
            }
            return entries.slice(0, 40);
          };

          const windowKeys = Object.keys(window)
            .filter((key) => pattern.test(key))
            .slice(0, 80);
          const windowSnapshot = Object.fromEntries(
            windowKeys.slice(0, 30).map((key) => [key, summarize(window[key])]),
          );

          const vmInjectSnapshot = {};
          if (vm) {
            for (const key of Object.keys(vm)) {
              if (key.startsWith('_')) continue;
              if (!pattern.test(key)) continue;
              vmInjectSnapshot[key] = summarize(vm[key]);
            }
          }

          return {
            component_found: !!vm,
            local_storage_entries: readStorage(window.localStorage),
            session_storage_entries: readStorage(window.sessionStorage),
            window_keys: windowKeys,
            window_snapshot: windowSnapshot,
            vm_inject_snapshot: vmInjectSnapshot,
          };
        }""",
        component_name,
    )


def _capture_component_injection_context(frame, *, component_name: str) -> dict[str, Any]:
    return frame.evaluate(
        """(componentName) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;

          const summarizeValue = (value) => {
            if (value === null || value === undefined) return null;
            if (typeof value === 'function') return { type: 'function' };
            if (Array.isArray(value)) {
              return {
                type: 'array',
                length: value.length,
                first_row: value.length ? value[0] : null,
              };
            }
            if (typeof value === 'object') {
              return {
                type: 'object',
                keys: Object.keys(value).slice(0, 20),
              };
            }
            return value;
          };

          const summarizeRoute = (route) => {
            if (!route || typeof route !== 'object') return null;
            return {
              name: route.name || null,
              path: route.path || null,
              fullPath: route.fullPath || null,
              hash: route.hash || null,
              query: route.query || null,
              params: route.params || null,
            };
          };

          const summarizeDetailData = (detailData) => {
            if (!detailData || typeof detailData !== 'object') return null;
            return {
              currentItem: detailData.currentItem || null,
              keyword: detailData.keyword || '',
              columnType: detailData.columnType,
              pager: detailData.pager
                ? {
                    page: detailData.pager.page ?? null,
                    pageSize: detailData.pager.pageSize ?? null,
                    total: detailData.pager.total ?? null,
                  }
                : null,
              extraHeaderLabels: summarizeValue(detailData.extraHeaderLabels),
              extraHeader: summarizeValue(detailData.extraHeader),
              baseHeaders: summarizeValue(detailData.baseHeaders),
              totalLines: summarizeValue(detailData.totalLines),
            };
          };

          const summarizeEventHub = (hub) => {
            if (!hub || typeof hub !== 'object') return null;
            const eventKeys = hub._events && typeof hub._events === 'object'
              ? Object.keys(hub._events).slice(0, 40)
              : [];
            return {
              keys: Object.keys(hub).slice(0, 30),
              event_keys: eventKeys,
            };
          };

          const summarizeEditableTabs = (tabs) => {
            if (!Array.isArray(tabs)) return { type: 'array', length: 0, sample_rows: [] };
            return {
              type: 'array',
              length: tabs.length,
              sample_rows: tabs.slice(0, 3),
            };
          };

          if (!vm) return { component_found: false };

          const parent = vm.$parent || null;
          const root = vm.$root || null;
          const rootData = root?._data || {};
          return {
            component_found: true,
            route_snapshot: summarizeRoute(vm.$route || root?.$route || null),
            detail_data_snapshot: summarizeDetailData(vm.detailData || null),
            shell_context: parent
              ? {
                  component_name: parent.$options?.name || parent.$options?._componentTag || null,
                  menuItemId: parent.menuItemId || null,
                  editableTabs: summarizeEditableTabs(parent.editableTabs),
                  reportLists: summarizeValue(parent.reportLists),
                  reportArrList: summarizeValue(parent.reportArrList),
                  invoicesLists: summarizeValue(parent.invoicesLists),
                  invoicesArrList: summarizeValue(parent.invoicesArrList),
                }
              : null,
            root_event_hub: summarizeEventHub(rootData.yisEventHub || null),
          };
        }""",
        component_name,
    )


def _capture_component_method_sources(
    frame,
    *,
    component_name: str,
    method_names: tuple[str, ...],
) -> dict[str, Any]:
    return frame.evaluate(
        r"""([componentName, methodNames]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          if (!vm) return { component_found: false, methods: {} };
          const normalizeText = (value) => String(value).replace(/\s+/g, ' ').trim();
          const methods = {};
          for (const methodName of methodNames) {
            const method = vm[methodName];
            if (typeof method !== 'function') continue;
            let source = '';
            try {
              source = String(method);
            } catch (error) {
              source = `__stringify_error__:${String(error)}`;
            }
            methods[methodName] = {
              length: source.length,
              preview: normalizeText(source).slice(0, 600),
            };
          }
          return {
            component_found: true,
            component_name: vm.$options?.name || vm.$options?._componentTag || null,
            methods,
          };
        }""",
        [component_name, list(method_names)],
    )


def _capture_nested_row_context(frame, *, component_name: str, nested_component_name: str | None = None) -> dict[str, Any]:
    return frame.evaluate(
        """([componentName, nestedComponentName]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          const all = nodes.filter((node) => node.__vue__).map((node) => node.__vue__);
          const nestedCandidates = all.filter((candidate) => candidate !== vm);
          const namedNested = nestedComponentName
            ? nestedCandidates.find((candidate) => (candidate.$options?.name || '') === nestedComponentName)
            : null;
          const dataNested = nestedCandidates.find((candidate) => {
            const tableData = candidate?.vxeTable?.tableData || candidate?.tableData || null;
            return Array.isArray(tableData) && tableData.length > 0;
          });
          const nested = namedNested || dataNested || null;
          const tableData = nested?.vxeTable?.tableData || nested?.tableData || [];
          const firstRow = Array.isArray(tableData) && tableData.length ? tableData[0] : null;
          const rowState = {};
          if (vm) {
            for (const key of Object.keys(vm)) {
              if (key.startsWith('_')) continue;
              if (!/(select|row|item|current|detail|order)/i.test(key)) continue;
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
        [component_name, nested_component_name],
    )


def _capture_ref_component_state(frame, *, component_name: str, ref_name: str) -> dict[str, Any]:
    return frame.evaluate(
        """([componentName, refName, pattern]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          const summarizeValue = (value) => {
            if (value === null || value === undefined) return null;
            if (typeof value === 'function') return { type: 'function' };
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
                keys: Object.keys(value).slice(0, 20),
              };
            }
            return value;
          };
          const target = (() => {
            const raw = vm?.$refs?.[refName];
            if (Array.isArray(raw)) return raw[0] || null;
            return raw || null;
          })();
          if (!target || typeof target !== 'object') {
            return { ref_found: false };
          }
          const matchedKeys = Object.keys(target)
            .filter((key) => !key.startsWith('_') && !key.startsWith('$'))
            .filter((key) => new RegExp(pattern, 'i').test(key))
            .slice(0, 40);
          const snapshot = {};
          for (const key of matchedKeys) {
            snapshot[key] = summarizeValue(target[key]);
          }
          const nestedSnapshots = {};
          for (const key of Object.keys(target).filter((key) => !key.startsWith('_') && !key.startsWith('$')).slice(0, 60)) {
            const value = target[key];
            if (!value || Array.isArray(value) || typeof value !== 'object') continue;
              const childKeys = Object.keys(value)
                .filter((childKey) => !childKey.startsWith('_') && !childKey.startsWith('$'))
                .filter((childKey) => new RegExp(pattern, 'i').test(childKey))
                .slice(0, 24);
            if (!childKeys.length) continue;
            nestedSnapshots[key] = Object.fromEntries(childKeys.map((childKey) => [childKey, summarizeValue(value[childKey])]));
          }
          const refRefs = {};
          if (target.$refs) {
            for (const [childRefKey, childRefValue] of Object.entries(target.$refs).slice(0, 20)) {
              const childTarget = Array.isArray(childRefValue) ? childRefValue[0] : childRefValue;
              if (!childTarget || typeof childTarget !== 'object') continue;
              const childKeys = Object.keys(childTarget)
                .filter((key) => !key.startsWith('_') && !key.startsWith('$'))
                .filter((key) => new RegExp(pattern, 'i').test(key))
                .slice(0, 20);
              refRefs[childRefKey] = {
                component_name: childTarget.$options?.name || childTarget.$options?._componentTag || null,
                snapshot: Object.fromEntries(childKeys.map((key) => [key, summarizeValue(childTarget[key])])),
              };
            }
          }
          const propsData = target.$options?.propsData || {};
          const specialSnapshot = {
            props_keys: target.$options?.props ? Object.keys(target.$options.props).slice(0, 20) : [],
            props_data_keys: Object.keys(propsData).slice(0, 20),
            props_data_snapshot: Object.fromEntries(
              Object.entries(propsData)
                .slice(0, 20)
                .map(([key, value]) => [key, summarizeValue(value)]),
            ),
            watcher_expressions: Array.isArray(target._watchers)
              ? target._watchers
                  .map((watcher) => watcher?.expression || watcher?.getter?.name || '')
                  .filter(Boolean)
                  .slice(0, 20)
              : [],
            computed_watcher_keys: target._computedWatchers ? Object.keys(target._computedWatchers).slice(0, 20) : [],
          };
          if ('detailData' in target) {
            specialSnapshot.detailData = summarizeValue(target.detailData);
          }
          if (target?.detailData && typeof target.detailData === 'object') {
            specialSnapshot.detailData_snapshot = Object.fromEntries(
              Object.entries(target.detailData)
                .slice(0, 20)
                .map(([key, value]) => [key, summarizeValue(value)]),
            );
          }
          if ('currentItem' in target) {
            specialSnapshot.currentItem = summarizeValue(target.currentItem);
          }
          return {
            ref_found: true,
            ref_name: refName,
            component_name: target.$options?.name || target.$options?._componentTag || null,
            matched_keys: matchedKeys,
            snapshot,
            nested_snapshots: nestedSnapshots,
            child_refs: refRefs,
            special_snapshot: specialSnapshot,
          };
        }""",
        [component_name, ref_name, COMPONENT_FIELD_PATTERN],
    )


def _capture_child_ref_component_state(
    frame,
    *,
    component_name: str,
    ref_name: str,
    child_ref_name: str,
) -> dict[str, Any]:
    return frame.evaluate(
        """([componentName, refName, childRefName, pattern]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          const summarizeValue = (value) => {
            if (value === null || value === undefined) return null;
            if (typeof value === 'function') return { type: 'function' };
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
                keys: Object.keys(value).slice(0, 20),
              };
            }
            return value;
          };
          const parentRaw = vm?.$refs?.[refName];
          const parentTarget = Array.isArray(parentRaw) ? parentRaw[0] : parentRaw;
          const childRaw = parentTarget?.$refs?.[childRefName];
          const childTarget = Array.isArray(childRaw) ? childRaw[0] : childRaw;
          if (!childTarget || typeof childTarget !== 'object') {
            return { child_ref_found: false };
          }
          const matchedKeys = Object.keys(childTarget)
            .filter((key) => !key.startsWith('_') && !key.startsWith('$'))
            .filter((key) => new RegExp(pattern, 'i').test(key))
            .slice(0, 40);
          const snapshot = {};
          for (const key of matchedKeys) {
            snapshot[key] = summarizeValue(childTarget[key]);
          }
          const nestedSnapshots = {};
          for (const key of matchedKeys) {
            const value = childTarget[key];
            if (!value || Array.isArray(value) || typeof value !== 'object') continue;
            const childKeys = Object.keys(value)
              .filter((childKey) => !childKey.startsWith('_') && !childKey.startsWith('$'))
              .slice(0, 30);
            if (!childKeys.length) continue;
            nestedSnapshots[key] = Object.fromEntries(
              childKeys.map((childKey) => [childKey, summarizeValue(value[childKey])]),
            );
          }
          const propsData = childTarget.$options?.propsData || {};
          const specialSnapshot = {
            props_keys: childTarget.$options?.props ? Object.keys(childTarget.$options.props).slice(0, 20) : [],
            props_data_keys: Object.keys(propsData).slice(0, 20),
            props_data_snapshot: Object.fromEntries(
              Object.entries(propsData)
                .slice(0, 20)
                .map(([key, value]) => [key, summarizeValue(value)]),
            ),
            watcher_expressions: Array.isArray(childTarget._watchers)
              ? childTarget._watchers
                  .map((watcher) => watcher?.expression || watcher?.getter?.name || '')
                  .filter(Boolean)
                  .slice(0, 20)
              : [],
            computed_watcher_keys: childTarget._computedWatchers ? Object.keys(childTarget._computedWatchers).slice(0, 20) : [],
          };
          if ('allTableData' in childTarget) {
            specialSnapshot.allTableData = summarizeValue(childTarget.allTableData);
          }
          if ('tableData' in childTarget) {
            specialSnapshot.tableData = summarizeValue(childTarget.tableData);
          }
          if (childTarget.vxeTable && typeof childTarget.vxeTable === 'object') {
            const vxe = childTarget.vxeTable;
            const database = vxe.database && typeof vxe.database === 'object'
              ? Object.fromEntries(
                  Object.entries(vxe.database)
                    .slice(0, 20)
                    .map(([key, value]) => [key, summarizeValue(value)]),
                )
              : null;
            specialSnapshot.vxeTable_snapshot = {
              keys: Object.keys(vxe).slice(0, 40),
              tableData: summarizeValue(vxe.tableData),
              viewData: summarizeValue(vxe.viewData),
              initHeaderData: summarizeValue(vxe.initHeaderData),
              orderByData: summarizeValue(vxe.orderByData),
              tableSumData: summarizeValue(vxe.tableSumData),
              tableSubtotalData: summarizeValue(vxe.tableSubtotalData),
              database: summarizeValue(vxe.database),
              database_snapshot: database,
              tablePage: summarizeValue(vxe.tablePage),
            };
          }
          return {
            child_ref_found: true,
            parent_ref_name: refName,
            child_ref_name: childRefName,
            component_name: childTarget.$options?.name || childTarget.$options?._componentTag || null,
            matched_keys: matchedKeys,
            snapshot,
            nested_snapshots: nestedSnapshots,
            special_snapshot: specialSnapshot,
          };
        }""",
        [component_name, ref_name, child_ref_name, COMPONENT_FIELD_PATTERN],
    )


def _capture_child_ref_indexeddb_state(
    frame,
    *,
    component_name: str,
    ref_name: str,
    child_ref_name: str,
) -> dict[str, Any]:
    return frame.evaluate(
        """async ([componentName, refName, childRefName]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          if (!vm) return { component_found: false };

          const parentRaw = vm.$refs?.[refName];
          const parentTarget = Array.isArray(parentRaw) ? parentRaw[0] : parentRaw;
          const childRaw = parentTarget?.$refs?.[childRefName];
          const childTarget = Array.isArray(childRaw) ? childRaw[0] : childRaw;
          if (!childTarget || typeof childTarget !== 'object') {
            return { component_found: true, child_ref_found: false };
          }

          const databaseTableName = childTarget.$options?.propsData?.databaseTableName || null;
          const databaseName = childTarget?.vxeTable?.database?.DateBaseName || null;
          const version = childTarget?.vxeTable?.database?.Version || null;

          const summarize = (value) => {
            if (value === null || value === undefined) return null;
            if (Array.isArray(value)) return { type: 'array', length: value.length, sample: value.slice(0, 5) };
            if (typeof value === 'object') return { type: 'object', keys: Object.keys(value).slice(0, 20) };
            return value;
          };

          const response = {
            component_found: true,
            child_ref_found: true,
            database_name: databaseName,
            database_table_name: databaseTableName,
            database_version: version,
            indexeddb_supported: typeof indexedDB !== 'undefined',
            databases_api_supported: typeof indexedDB?.databases === 'function',
            databases: [],
            target_database: null,
          };
          if (typeof indexedDB === 'undefined') return response;

          if (typeof indexedDB.databases === 'function') {
            try {
              const dbs = await indexedDB.databases();
              response.databases = (dbs || []).map((item) => ({
                name: item?.name || null,
                version: item?.version || null,
              }));
            } catch (error) {
              response.databases_error = String(error);
            }
          }

          if (!databaseName) return response;

          const openDatabase = () => new Promise((resolve) => {
            const request = indexedDB.open(databaseName);
            request.onerror = () => resolve({ open_error: String(request.error || 'indexeddb_open_failed') });
            request.onsuccess = () => resolve({ db: request.result });
          });

          const opened = await openDatabase();
          if (!opened?.db) {
            response.target_database = opened;
            return response;
          }

          const db = opened.db;
          const storeNames = Array.from(db.objectStoreNames || []);
          const countStore = (storeName) => new Promise((resolve) => {
            try {
              const tx = db.transaction(storeName, 'readonly');
              const store = tx.objectStore(storeName);
              const request = store.count();
              request.onerror = () => resolve({ store_name: storeName, count_error: String(request.error || 'count_failed') });
              request.onsuccess = () => resolve({ store_name: storeName, count: request.result });
            } catch (error) {
              resolve({ store_name: storeName, count_error: String(error) });
            }
          });

          const stores = [];
          for (const storeName of storeNames.slice(0, 20)) {
            stores.push(await countStore(storeName));
          }

          response.target_database = {
            name: db.name,
            version: db.version,
            object_store_names: storeNames,
            stores,
            target_store: databaseTableName && storeNames.includes(databaseTableName)
              ? stores.find((item) => item.store_name === databaseTableName) || null
              : null,
            browser_db_meta: summarize(childTarget?.vxeTable?.database),
          };
          db.close();
          return response;
        }""",
        [component_name, ref_name, child_ref_name],
    )


def _capture_child_ref_websql_state(
    frame,
    *,
    component_name: str,
    ref_name: str,
    child_ref_name: str,
) -> dict[str, Any]:
    return frame.evaluate(
        """async ([componentName, refName, childRefName]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          if (!vm) return { component_found: false };

          const parentRaw = vm.$refs?.[refName];
          const parentTarget = Array.isArray(parentRaw) ? parentRaw[0] : parentRaw;
          const childRaw = parentTarget?.$refs?.[childRefName];
          const childTarget = Array.isArray(childRaw) ? childRaw[0] : childRaw;
          if (!childTarget || typeof childTarget !== 'object') {
            return { component_found: true, child_ref_found: false };
          }

          const databaseMeta = childTarget?.vxeTable?.database || {};
          const databaseName = databaseMeta?.DateBaseName || null;
          const databaseVersion = Number.parseFloat(databaseMeta?.Version || '1') || 1;
          const databaseDescription = databaseMeta?.Description || '';
          const databaseSize = Number(databaseMeta?.DataBaseSize || 0) || 0;
          const tableName = childTarget.$options?.propsData?.databaseTableName || null;

          const response = {
            component_found: true,
            child_ref_found: true,
            websql_supported: typeof openDatabase === 'function',
            database_name: databaseName,
            database_version: databaseVersion,
            database_description: databaseDescription,
            database_size: databaseSize,
            database_table_name: tableName,
            tables: [],
            target_table: null,
          };
          if (typeof openDatabase !== 'function' || !databaseName) return response;

          const runSql = (db, sql, args = []) => new Promise((resolve) => {
            try {
              db.readTransaction((tx) => {
                tx.executeSql(
                  sql,
                  args,
                  (_tx, result) => {
                    const rows = [];
                    const rawRows = result?.rows;
                    const length = rawRows?.length || 0;
                    for (let i = 0; i < Math.min(length, 5); i += 1) {
                      rows.push(rawRows.item(i));
                    }
                    resolve({
                      ok: true,
                      rows,
                      rows_length: length,
                    });
                  },
                  (_tx, error) => {
                    resolve({
                      ok: false,
                      error: String(error?.message || error || 'sql_failed'),
                    });
                    return true;
                  },
                );
              });
            } catch (error) {
              resolve({
                ok: false,
                error: String(error),
              });
            }
          });

          try {
            const db = openDatabase(databaseName, String(databaseVersion), databaseDescription || databaseName, databaseSize || 20 * 1024 * 1024);
            const tablesResult = await runSql(
              db,
              "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"
            );
            response.tables = tablesResult?.rows || [];
            if (tableName) {
              const targetRows = await runSql(db, `SELECT * FROM "${tableName}" LIMIT 5`);
              const targetCount = await runSql(db, `SELECT COUNT(*) AS row_count FROM "${tableName}"`);
              response.target_table = {
                name: tableName,
                select_result: targetRows,
                count_result: targetCount,
              };
            }
          } catch (error) {
            response.open_error = String(error);
          }
          return response;
        }""",
        [component_name, ref_name, child_ref_name],
    )


def _capture_ref_method_sources(
    frame,
    *,
    component_name: str,
    ref_name: str,
    method_names: tuple[str, ...],
) -> dict[str, Any]:
    return frame.evaluate(
        r"""([componentName, refName, methodNames]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          if (!vm) return { component_found: false, ref_found: false, methods: {} };
          const raw = vm.$refs?.[refName];
          const target = Array.isArray(raw) ? raw[0] : raw;
          if (!target || typeof target !== 'object') {
            return { component_found: true, ref_found: false, methods: {} };
          }
          const normalizeText = (value) => String(value).replace(/\s+/g, ' ').trim();
          const methods = {};
          for (const methodName of methodNames) {
            const method = target[methodName];
            if (typeof method !== 'function') continue;
            let source = '';
            try {
              source = String(method);
            } catch (error) {
              source = `__stringify_error__:${String(error)}`;
            }
            methods[methodName] = {
              length: source.length,
              preview: normalizeText(source).slice(0, 600),
            };
          }
          return {
            component_found: true,
            ref_found: true,
            component_name: target.$options?.name || target.$options?._componentTag || null,
            methods,
          };
        }""",
        [component_name, ref_name, list(method_names)],
    )


def _capture_child_ref_method_sources(
    frame,
    *,
    component_name: str,
    ref_name: str,
    child_ref_name: str,
    method_names: tuple[str, ...],
) -> dict[str, Any]:
    return frame.evaluate(
        r"""([componentName, refName, childRefName, methodNames]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          if (!vm) return { component_found: false, child_ref_found: false, methods: {} };
          const parentRaw = vm.$refs?.[refName];
          const parentTarget = Array.isArray(parentRaw) ? parentRaw[0] : parentRaw;
          const childRaw = parentTarget?.$refs?.[childRefName];
          const childTarget = Array.isArray(childRaw) ? childRaw[0] : childRaw;
          if (!childTarget || typeof childTarget !== 'object') {
            return { component_found: true, child_ref_found: false, methods: {} };
          }
          const normalizeText = (value) => String(value).replace(/\s+/g, ' ').trim();
          const methods = {};
          for (const methodName of methodNames) {
            const method = childTarget[methodName];
            if (typeof method !== 'function') continue;
            let source = '';
            try {
              source = String(method);
            } catch (error) {
              source = `__stringify_error__:${String(error)}`;
            }
            methods[methodName] = {
              length: source.length,
              preview: normalizeText(source).slice(0, 600),
            };
          }
          return {
            component_found: true,
            child_ref_found: true,
            component_name: childTarget.$options?.name || childTarget.$options?._componentTag || null,
            methods,
          };
        }""",
        [component_name, ref_name, child_ref_name, list(method_names)],
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
    component_name: str | None = None,
    nested_component_name: str | None = None,
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
    if component_name:
        step["page_component_state_after"] = _capture_local_component_state(
            frame,
            component_name=component_name,
            nested_component_name=nested_component_name,
        )
        step["component_ancestry_after"] = _capture_component_ancestry(
            frame,
            component_name=component_name,
        )
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
    nested_component_name: str | None = None,
    call_mode: str = "none",
    seed_selection_fields: tuple[str, ...] = (),
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    collector.set_action(f"component_method_{method_name}")
    counts = collector.snapshot_counts()
    local_state_before = _capture_local_component_state(
        frame,
        component_name=component_name,
        nested_component_name=nested_component_name,
    )
    nested_row_context_before = _capture_nested_row_context(
        frame,
        component_name=component_name,
        nested_component_name=nested_component_name,
    )
    invocation = frame.evaluate(
        """async ([componentName, methodName, nestedComponentName, callMode, seedSelectionFields]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          if (!vm) {
            return { component_found: false, method_found: false, invoked: false };
          }
          const all = nodes.filter((node) => node.__vue__).map((node) => node.__vue__);
          const nestedCandidates = all.filter((candidate) => candidate !== vm);
          const namedNested = nestedComponentName
            ? nestedCandidates.find((candidate) => (candidate.$options?.name || '') === nestedComponentName)
            : null;
          const dataNested = nestedCandidates.find((candidate) => {
            const tableData = candidate?.vxeTable?.tableData || candidate?.tableData || null;
            return Array.isArray(tableData) && tableData.length > 0;
          });
          const nested = namedNested || dataNested || null;
          const tableData = nested?.vxeTable?.tableData || nested?.tableData || [];
          const firstRow = Array.isArray(tableData) && tableData.length ? tableData[0] : null;
          if (firstRow && Array.isArray(seedSelectionFields)) {
            for (const field of seedSelectionFields) {
              if (!(field in vm)) continue;
              const value = vm[field];
              if (Array.isArray(value)) {
                vm[field] = value.length ? value : [firstRow];
              } else if (value == null || value === '' || (typeof value === 'object' && !Object.keys(value).length)) {
                vm[field] = firstRow;
              }
            }
          }
          const method = vm[methodName];
          if (typeof method !== 'function') {
            return { component_found: true, method_found: false, invoked: false, first_row: firstRow };
          }
          try {
            let result;
            if (callMode === 'row') {
              result = method.call(vm, firstRow);
            } else if (callMode === 'row_list') {
              result = method.call(vm, firstRow ? [firstRow] : []);
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
              first_row: firstRow,
              call_mode: callMode,
            };
          } catch (error) {
            return {
              component_found: true,
              method_found: true,
              invoked: false,
              first_row: firstRow,
              call_mode: callMode,
              error: String(error),
            };
          }
        }""",
        [component_name, method_name, nested_component_name, call_mode, list(seed_selection_fields)],
    )
    page.wait_for_timeout(wait_ms)
    delta = collector.collect_since(counts)
    step = {
        "key": f"component_method_{method_name}",
        "step": f"component_method_{method_name}",
        "captured_at": now_local().isoformat(),
        "action_triggered": bool(invocation.get("invoked")),
        "component_invocation": invocation,
        "local_state_before": local_state_before,
        "nested_row_context_before": nested_row_context_before,
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
        "component_ancestry_after": _capture_component_ancestry(
            frame,
            component_name=component_name,
        ),
        "nested_row_context_after": _capture_nested_row_context(
            frame,
            component_name=component_name,
            nested_component_name=nested_component_name,
        ),
        "local_state_after": _capture_local_component_state(
            frame,
            component_name=component_name,
            nested_component_name=nested_component_name,
        ),
    }
    return step, previous_requests + delta.get("requests", [])


def _run_ref_method_probe(
    *,
    page,
    frame,
    collector: NetworkCollector,
    component_name: str,
    ref_name: str,
    method_name: str,
    wait_ms: int,
    previous_requests: list[dict[str, Any]],
    scope_texts: tuple[str, ...],
    scope_action_texts: tuple[str, ...],
    nested_component_name: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    collector.set_action(f"ref_method_{ref_name}_{method_name}")
    counts = collector.snapshot_counts()
    local_state_before = _capture_local_component_state(
        frame,
        component_name=component_name,
        nested_component_name=nested_component_name,
    )
    ref_state_before = _capture_ref_component_state(frame, component_name=component_name, ref_name=ref_name)
    invocation = frame.evaluate(
        """async ([componentName, refName, methodName]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          if (!vm) return { component_found: false, ref_found: false, method_found: false, invoked: false };
          const raw = vm.$refs?.[refName];
          const target = Array.isArray(raw) ? raw[0] : raw;
          if (!target || typeof target !== 'object') {
            return { component_found: true, ref_found: false, method_found: false, invoked: false };
          }
          const method = target[methodName];
          if (typeof method !== 'function') {
            return { component_found: true, ref_found: true, method_found: false, invoked: false };
          }
          try {
            let result = method.call(target);
            if (result && typeof result.then === 'function') {
              await result;
            }
            return {
              component_found: true,
              ref_found: true,
              method_found: true,
              invoked: true,
            };
          } catch (error) {
            return {
              component_found: true,
              ref_found: true,
              method_found: true,
              invoked: false,
              error: String(error),
            };
          }
        }""",
        [component_name, ref_name, method_name],
    )
    page.wait_for_timeout(wait_ms)
    delta = collector.collect_since(counts)
    step = {
        "key": f"ref_method_{ref_name}_{method_name}",
        "step": f"ref_method_{ref_name}_{method_name}",
        "captured_at": now_local().isoformat(),
        "action_triggered": bool(invocation.get("invoked")),
        "ref_invocation": invocation,
        "local_state_before": local_state_before,
        "ref_state_before": ref_state_before,
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
        "component_ancestry_after": _capture_component_ancestry(
            frame,
            component_name=component_name,
        ),
        "local_state_after": _capture_local_component_state(
            frame,
            component_name=component_name,
            nested_component_name=nested_component_name,
        ),
        "ref_state_after": _capture_ref_component_state(frame, component_name=component_name, ref_name=ref_name),
    }
    return step, previous_requests + delta.get("requests", [])


def _run_child_ref_method_probe(
    *,
    page,
    frame,
    collector: NetworkCollector,
    component_name: str,
    ref_name: str,
    child_ref_name: str,
    method_name: str,
    wait_ms: int,
    previous_requests: list[dict[str, Any]],
    scope_texts: tuple[str, ...],
    scope_action_texts: tuple[str, ...],
    nested_component_name: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    collector.set_action(f"child_ref_method_{ref_name}_{child_ref_name}_{method_name}")
    counts = collector.snapshot_counts()
    local_state_before = _capture_local_component_state(
        frame,
        component_name=component_name,
        nested_component_name=nested_component_name,
    )
    child_ref_state_before = _capture_child_ref_component_state(
        frame,
        component_name=component_name,
        ref_name=ref_name,
        child_ref_name=child_ref_name,
    )
    child_ref_indexeddb_before = _capture_child_ref_indexeddb_state(
        frame,
        component_name=component_name,
        ref_name=ref_name,
        child_ref_name=child_ref_name,
    )
    child_ref_websql_before = _capture_child_ref_websql_state(
        frame,
        component_name=component_name,
        ref_name=ref_name,
        child_ref_name=child_ref_name,
    )
    invocation = frame.evaluate(
        """async ([componentName, refName, childRefName, methodName]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          if (!vm) return { component_found: false, child_ref_found: false, method_found: false, invoked: false };
          const parentRaw = vm.$refs?.[refName];
          const parentTarget = Array.isArray(parentRaw) ? parentRaw[0] : parentRaw;
          const childRaw = parentTarget?.$refs?.[childRefName];
          const childTarget = Array.isArray(childRaw) ? childRaw[0] : childRaw;
          if (!childTarget || typeof childTarget !== 'object') {
            return { component_found: true, child_ref_found: false, method_found: false, invoked: false };
          }
          const method = childTarget[methodName];
          if (typeof method !== 'function') {
            return { component_found: true, child_ref_found: true, method_found: false, invoked: false };
          }
          try {
            let result = method.call(childTarget);
            if (result && typeof result.then === 'function') {
              await result;
            }
            return { component_found: true, child_ref_found: true, method_found: true, invoked: true };
          } catch (error) {
            return {
              component_found: true,
              child_ref_found: true,
              method_found: true,
              invoked: false,
              error: String(error),
            };
          }
        }""",
        [component_name, ref_name, child_ref_name, method_name],
    )
    page.wait_for_timeout(wait_ms)
    delta = collector.collect_since(counts)
    step = {
        "key": f"child_ref_method_{ref_name}_{child_ref_name}_{method_name}",
        "step": f"child_ref_method_{ref_name}_{child_ref_name}_{method_name}",
        "captured_at": now_local().isoformat(),
        "action_triggered": bool(invocation.get("invoked")),
        "child_ref_invocation": invocation,
        "local_state_before": local_state_before,
        "child_ref_state_before": child_ref_state_before,
        "child_ref_indexeddb_before": child_ref_indexeddb_before,
        "child_ref_websql_before": child_ref_websql_before,
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
        "component_ancestry_after": _capture_component_ancestry(
            frame,
            component_name=component_name,
        ),
        "local_state_after": _capture_local_component_state(
            frame,
            component_name=component_name,
            nested_component_name=nested_component_name,
        ),
        "child_ref_state_after": _capture_child_ref_component_state(
            frame,
            component_name=component_name,
            ref_name=ref_name,
            child_ref_name=child_ref_name,
        ),
        "child_ref_indexeddb_after": _capture_child_ref_indexeddb_state(
            frame,
            component_name=component_name,
            ref_name=ref_name,
            child_ref_name=child_ref_name,
        ),
        "child_ref_websql_after": _capture_child_ref_websql_state(
            frame,
            component_name=component_name,
            ref_name=ref_name,
            child_ref_name=child_ref_name,
        ),
    }
    return step, previous_requests + delta.get("requests", [])


def main() -> int:
    parser = argparse.ArgumentParser(description="对 Yeusoft 收货确认页面做 UI 动作链取证，抓取选中行与二级按钮后的真实请求变化")
    parser.add_argument("--site-url", default="https://jypos.yeusoft.net/")
    parser.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--analysis-root", default=str(PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--wait-ms", type=int, default=NETWORK_WAIT_MS)
    args = parser.parse_args()

    entry = _resolve_page_entry("收货确认", Path(args.analysis_root))
    sync_playwright, _ = import_playwright()

    run_dir = Path(args.output_root) / f"{now_local().strftime('%Y%m%d-%H%M%S')}-receipt-confirmation-ui-probe"
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
                raise RuntimeError("未在菜单树中找到收货确认")

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
                    "ref_method_probes": [],
                    "child_ref_method_probes": [],
                    "ref_method_sources": [],
                    "child_ref_method_sources": [],
                }

                open_step, previous_requests = _run_probe_action(
                    page=page,
                    frame=frame,
                    collector=collector,
                    action_key="open_receipt_confirmation",
                    callback=lambda: bool(open_report_by_menu_item(frame, page, menu_item) or True),
                    wait_ms=args.wait_ms,
                    previous_requests=previous_requests,
                    scope_texts=scope_texts,
                    scope_action_texts=scope_action_texts,
                    component_name=COMPONENT_NAME,
                    nested_component_name=NESTED_TABLE_COMPONENT,
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
                result["baseline"]["component_ancestry_after_open"] = _capture_component_ancestry(
                    frame,
                    component_name=COMPONENT_NAME,
                )
                result["baseline"]["component_store_after_open"] = _capture_component_store_state(
                    frame,
                    component_name=COMPONENT_NAME,
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
                    wait_ms=args.wait_ms,
                    previous_requests=previous_requests,
                    scope_texts=scope_texts,
                    scope_action_texts=scope_action_texts,
                    component_name=COMPONENT_NAME,
                    nested_component_name=NESTED_TABLE_COMPONENT,
                )
                result["baseline"]["query_step"] = query_step
                result["baseline"]["component_state_after_query"] = capture_component_state(
                    frame,
                    scope_texts=scope_texts,
                    action_texts=scope_action_texts,
                )
                result["baseline"]["component_ancestry_after_query"] = _capture_component_ancestry(
                    frame,
                    component_name=COMPONENT_NAME,
                )
                result["baseline"]["component_ancestry_ref_states_after_query"] = [
                    _capture_ancestry_ref_state(
                        frame,
                        component_name=COMPONENT_NAME,
                        depth=depth,
                        ref_name=ref_name,
                    )
                    for depth, ref_name in ANCESTRY_REF_PROBES
                ]
                result["baseline"]["component_ancestry_method_sources_after_query"] = _capture_ancestry_method_sources(
                    frame,
                    component_name=COMPONENT_NAME,
                )
                result["baseline"]["component_store_after_query"] = _capture_component_store_state(
                    frame,
                    component_name=COMPONENT_NAME,
                )
                result["baseline"]["component_global_storage_after_query"] = _capture_component_global_storage_state(
                    frame,
                    component_name=COMPONENT_NAME,
                )
                result["baseline"]["component_injection_context_after_query"] = _capture_component_injection_context(
                    frame,
                    component_name=COMPONENT_NAME,
                )
                result["baseline"]["component_method_sources"] = _capture_component_method_sources(
                    frame,
                    component_name=COMPONENT_NAME,
                    method_names=COMPONENT_METHOD_SOURCE_NAMES,
                )
                result["baseline"]["local_state_after_query"] = _capture_local_component_state(
                    frame,
                    component_name=COMPONENT_NAME,
                    nested_component_name=NESTED_TABLE_COMPONENT,
                )
                result["baseline"]["nested_row_context_after_query"] = _capture_nested_row_context(
                    frame,
                    component_name=COMPONENT_NAME,
                    nested_component_name=NESTED_TABLE_COMPONENT,
                )
                result["baseline"]["child_ref_indexeddb_after_query"] = _capture_child_ref_indexeddb_state(
                    frame,
                    component_name=COMPONENT_NAME,
                    ref_name="reportTableItem_mainRef",
                    child_ref_name="RTM_reportTable",
                )
                result["baseline"]["child_ref_websql_after_query"] = _capture_child_ref_websql_state(
                    frame,
                    component_name=COMPONENT_NAME,
                    ref_name="reportTableItem_mainRef",
                    child_ref_name="RTM_reportTable",
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
                        component_name=COMPONENT_NAME,
                        nested_component_name=NESTED_TABLE_COMPONENT,
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
                        component_name=COMPONENT_NAME,
                        nested_component_name=NESTED_TABLE_COMPONENT,
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
                        wait_ms=2200,
                        previous_requests=previous_requests,
                        scope_texts=scope_texts,
                        scope_action_texts=scope_action_texts,
                        nested_component_name=NESTED_TABLE_COMPONENT,
                    )
                    result["component_method_probes"].append(method_step)

                component_selection_steps = (
                    ("tableSelectClick", "row"),
                    ("selectionChange", "row_list"),
                    ("checkDetail", "row"),
                    ("getDetailData", "row"),
                )
                for method_name, call_mode in component_selection_steps:
                    method_step, previous_requests = _run_component_method_probe(
                        page=page,
                        frame=frame,
                        collector=collector,
                        component_name=COMPONENT_NAME,
                        method_name=method_name,
                        wait_ms=2200,
                        previous_requests=previous_requests,
                        scope_texts=scope_texts,
                        scope_action_texts=scope_action_texts,
                        nested_component_name=NESTED_TABLE_COMPONENT,
                        call_mode=call_mode,
                        seed_selection_fields=SELECTION_FIELD_CANDIDATES,
                    )
                    result["component_method_probes"].append(method_step)

                for ref_name, method_name in REF_METHOD_PROBES:
                    ref_method_step, previous_requests = _run_ref_method_probe(
                        page=page,
                        frame=frame,
                        collector=collector,
                        component_name=COMPONENT_NAME,
                        ref_name=ref_name,
                        method_name=method_name,
                        wait_ms=2200,
                        previous_requests=previous_requests,
                        scope_texts=scope_texts,
                        scope_action_texts=scope_action_texts,
                        nested_component_name=NESTED_TABLE_COMPONENT,
                    )
                    result["ref_method_probes"].append(ref_method_step)

                for ref_name, method_names in REF_METHOD_SOURCE_NAMES:
                    result["ref_method_sources"].append(
                        _capture_ref_method_sources(
                            frame,
                            component_name=COMPONENT_NAME,
                            ref_name=ref_name,
                            method_names=method_names,
                        )
                    )

                for ref_name, child_ref_name, method_name in CHILD_REF_METHOD_PROBES:
                    child_ref_method_step, previous_requests = _run_child_ref_method_probe(
                        page=page,
                        frame=frame,
                        collector=collector,
                        component_name=COMPONENT_NAME,
                        ref_name=ref_name,
                        child_ref_name=child_ref_name,
                        method_name=method_name,
                        wait_ms=2200,
                        previous_requests=previous_requests,
                        scope_texts=scope_texts,
                        scope_action_texts=scope_action_texts,
                        nested_component_name=NESTED_TABLE_COMPONENT,
                    )
                    result["child_ref_method_probes"].append(child_ref_method_step)

                for ref_name, child_ref_name, method_names in CHILD_REF_METHOD_SOURCE_NAMES:
                    result["child_ref_method_sources"].append(
                        _capture_child_ref_method_sources(
                            frame,
                            component_name=COMPONENT_NAME,
                            ref_name=ref_name,
                            child_ref_name=child_ref_name,
                            method_names=method_names,
                        )
                    )

                safe_json_dump(page_dir / "manifest.json", result)
                analysis_path = Path(args.analysis_root) / f"receipt-confirmation-ui-probe-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
                safe_json_dump(analysis_path, result)
                print(json.dumps({"ok": True, "output": str(analysis_path)}, ensure_ascii=False))
            finally:
                collector.close()
        finally:
            context.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
