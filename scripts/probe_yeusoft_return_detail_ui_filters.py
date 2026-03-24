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
    extract_endpoint_name,
    fetch_menu_list,
    import_playwright,
    lookup_menu_item,
    now_local,
    open_report_by_menu_item,
    resolve_page_scope,
    safe_json_dump,
    wait_for_operational_frame,
    wait_for_operational_shell,
)


FILTER_OPTION_TEXTS: tuple[tuple[str, str], ...] = (
    ("品牌", "小黑托昵Black Tonny"),
    ("年份", "2026"),
    ("季节", "春"),
    ("大类", "衣着系列"),
    ("中类", "裤类"),
    ("小类", "单裤"),
    ("波段", "1a"),
)
PAGE_COMPONENT_NAME = "salesReturnDetailReport"
SAFE_COMPONENT_METHODS: tuple[str, ...] = ("RTM_searchConditions", "RTM_getReportInfo")
TABLE_REF_NAME = "RTM_reportTable"
TABLE_REF_METHOD_SOURCE_NAMES: tuple[str, ...] = (
    "searchConditions",
    "searchDataInfo",
    "pageCondition",
    "getReportInfo",
    "conditionStr",
)
ANCESTRY_METHOD_PATTERN = r"(return|report|search|query|filter|get|load|view|menu|grid|condition|operate|client|state|type|stock)"
ANCESTRY_REF_PROBES: tuple[tuple[int, str], ...] = (
    (0, "salesReturnDetail"),
    (1, "navmenu"),
)
CONTEXT_FIELD_PATTERN = (
    r"(return|stock|report|search|menu|type|order|arrive|ware|spen|state|year|season|brand|client|"
    r"current|item|data|page|total|grid|condition|query|filter)"
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
              .filter((key) => /(return|report|search|query|filter|stock|type|brand|year|season|state|order|arrive|ware|spen|menu|grid|condition|client)/i.test(key))
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


def _discover_method_owner_candidates(frame, *, method_names: tuple[str, ...]) -> list[dict[str, Any]]:
    return frame.evaluate(
        """(methodNames) => {
          const nodes = Array.from(document.querySelectorAll('*')).filter((node) => node.__vue__);
          const candidates = [];
          for (const node of nodes) {
            const vm = node.__vue__;
            const matchedMethods = (Array.isArray(methodNames) ? methodNames : []).filter(
              (methodName) => typeof vm?.[methodName] === 'function',
            );
            if (!matchedMethods.length) continue;
            const name = vm.$options?.name || vm.$options?._componentTag || 'anonymous';
            const ownKeys = Object.keys(vm).filter((key) => !key.startsWith('_') && !key.startsWith('$'));
            const matchedKeys = ownKeys
              .filter((key) => /(return|report|search|query|filter|stock|type|brand|year|season|state|order|arrive|ware|spen|menu|grid|condition)/i.test(key))
              .slice(0, 32);
            candidates.push({
              name,
              matched_methods: matchedMethods,
              matched_keys: matchedKeys,
              ref_count: vm.$refs ? Object.keys(vm.$refs).length : 0,
            });
          }
          return candidates.slice(0, 20);
        }""",
        list(method_names),
    )


def _capture_ancestry_ref_state(
    frame,
    *,
    component_name: str,
    depth: int,
    ref_name: str,
) -> dict[str, Any]:
    return frame.evaluate(
        """([componentName, depth, refName]) => {
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
            return { component_found: false, ancestor_found: false, ref_found: false };
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

          const matchedKeys = Object.keys(target)
            .filter((key) => !key.startsWith('_') && !key.startsWith('$'))
            .filter((key) => /(return|report|search|query|filter|stock|type|brand|year|season|state|order|arrive|ware|spen|menu|grid|condition|client)/i.test(key))
            .slice(0, 40);
          const snapshot = Object.fromEntries(
            matchedKeys.map((key) => [key, summarizeValue(target[key])]),
          );

          const propsData = target.$options?.propsData || {};
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
            props_data_snapshot: Object.fromEntries(
              Object.entries(propsData)
                .slice(0, 20)
                .map(([key, value]) => [key, summarizeValue(value)]),
            ),
            ref_keys: target.$refs ? Object.keys(target.$refs).slice(0, 20) : [],
          };
        }""",
        [component_name, depth, ref_name],
    )


def _capture_filter_component_diagnostics(frame) -> list[dict[str, Any]]:
    return frame.evaluate(
        """() => {
          const interestingKeys = [
            'TradeMarkCode',
            'Years',
            'Season',
            'CategoryCode',
            'TypeCode',
            'State',
            'PlatId',
            'Order',
            'ArriveStore',
            'warecause',
            'spenum',
            'type',
            'menuid',
            'gridid',
          ];
          const matchPattern = /trade|year|season|category|type|state|plat|order|arrive|ware|spen|menu|grid|brand|client/i;
          const nodes = Array.from(document.querySelectorAll('*')).filter((node) => node.__vue__);
          const items = [];
          for (const node of nodes) {
            const vm = node.__vue__;
            const name = vm.$options?.name || vm.$options?._componentTag || 'anonymous';
            const ownKeys = Object.keys(vm).filter((key) => !key.startsWith('_'));
            const matchedKeys = ownKeys.filter((key) => interestingKeys.includes(key) || matchPattern.test(key));
            const nestedMatches = [];
            for (const key of ownKeys) {
              const value = vm[key];
              if (!value || Array.isArray(value) || typeof value !== 'object') continue;
              const childKeys = Object.keys(value).filter((childKey) => interestingKeys.includes(childKey) || matchPattern.test(childKey));
              if (!childKeys.length) continue;
              nestedMatches.push({
                parent_key: key,
                child_keys: childKeys.slice(0, 20),
              });
            }
            if (!matchedKeys.length && !nestedMatches.length) continue;
            const snapshot = {};
            for (const key of matchedKeys.slice(0, 24)) {
              const value = vm[key];
              if (value === null || value === undefined) {
                snapshot[key] = null;
              } else if (Array.isArray(value)) {
                snapshot[key] = {
                  type: 'array',
                  length: value.length,
                  sample: value.slice(0, 2),
                };
              } else if (typeof value === 'object') {
                snapshot[key] = {
                  type: 'object',
                  keys: Object.keys(value).slice(0, 20),
                };
              } else {
                snapshot[key] = value;
              }
            }
            const nestedSnapshots = {};
            for (const nested of nestedMatches.slice(0, 12)) {
              const value = vm[nested.parent_key];
              const childSnapshot = {};
              for (const childKey of nested.child_keys.slice(0, 20)) {
                const childValue = value[childKey];
                if (childValue === null || childValue === undefined) {
                  childSnapshot[childKey] = null;
                } else if (Array.isArray(childValue)) {
                  childSnapshot[childKey] = {
                    type: 'array',
                    length: childValue.length,
                    sample: childValue.slice(0, 2),
                  };
                } else if (typeof childValue === 'object') {
                  childSnapshot[childKey] = {
                    type: 'object',
                    keys: Object.keys(childValue).slice(0, 20),
                  };
                } else {
                  childSnapshot[childKey] = childValue;
                }
              }
              nestedSnapshots[nested.parent_key] = childSnapshot;
            }
            items.push({
              name,
              matched_keys: matchedKeys.slice(0, 24),
              nested_matches: nestedMatches.slice(0, 12),
              snapshot,
              nested_snapshots: nestedSnapshots,
            });
          }
          return items.slice(0, 20);
        }""",
    )


def _capture_page_component_state(
    frame,
    *,
    component_name: str,
    fallback_method_names: tuple[str, ...] = (),
) -> dict[str, Any]:
    return frame.evaluate(
        """([componentName, fallbackMethodNames]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          let hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          if (!hit && Array.isArray(fallbackMethodNames) && fallbackMethodNames.length) {
            hit = nodes.find((node) => {
              const vm = node.__vue__;
              return fallbackMethodNames.some((methodName) => typeof vm?.[methodName] === 'function');
            }) || null;
          }
          const vm = hit?.__vue__ || null;
          const normalizeText = (value) => String(value || '').replace(/\\s+/g, ' ').trim().slice(0, 300);
          const summarizeValue = (value) => {
            if (value === null || value === undefined) return null;
            if (typeof value === 'function') {
              return {
                type: 'function',
              };
            }
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
          const collectMatchedKeys = (target) => {
            if (!target || typeof target !== 'object') return [];
            return Object.keys(target)
              .filter((key) => !key.startsWith('_') && !key.startsWith('$'))
              .filter((key) => /(search|query|filter|report|return|stock|type|brand|year|season|state|order|arrive|ware|spen|menu|grid|condition|client)/i.test(key))
              .slice(0, 48);
          };
          const snapshotObject = (target) => {
            const snapshot = {};
            for (const key of collectMatchedKeys(target)) {
              try {
                snapshot[key] = summarizeValue(target[key]);
              } catch (error) {
                snapshot[key] = { error: String(error) };
              }
            }
            return snapshot;
          };
          const snapshotNestedMatches = (target) => {
            const nestedSnapshots = {};
            if (!target || typeof target !== 'object') return nestedSnapshots;
            for (const key of Object.keys(target).filter((key) => !key.startsWith('_') && !key.startsWith('$')).slice(0, 64)) {
              const value = target[key];
              if (!value || Array.isArray(value) || typeof value !== 'object') continue;
              const childKeys = Object.keys(value)
                .filter((childKey) => !childKey.startsWith('_') && !childKey.startsWith('$'))
                .filter((childKey) => /(search|query|filter|report|return|stock|type|brand|year|season|state|order|arrive|ware|spen|menu|grid|condition|client)/i.test(childKey))
                .slice(0, 24);
              if (!childKeys.length) continue;
              const childSnapshot = {};
              for (const childKey of childKeys) {
                childSnapshot[childKey] = summarizeValue(value[childKey]);
              }
              nestedSnapshots[key] = childSnapshot;
            }
            return nestedSnapshots;
          };
          const safeMethodInfo = {};
          const safeMethodSources = {};
          if (vm) {
            for (const methodName of ['RTM_searchConditions', 'RTM_getReportInfo']) {
              const method = vm[methodName];
              safeMethodInfo[methodName] = typeof method === 'function';
              if (typeof method === 'function') {
                let source = '';
                try {
                  source = String(method);
                } catch (error) {
                  source = `__stringify_error__:${String(error)}`;
                }
                safeMethodSources[methodName] = {
                  length: source.length,
                  preview: normalizeText(source).slice(0, 500),
                };
              }
            }
          }
          const refsSnapshot = {};
          if (vm?.$refs) {
            for (const [refKey, refValue] of Object.entries(vm.$refs).slice(0, 20)) {
              const target = Array.isArray(refValue) ? refValue[0] : refValue;
              if (!target || typeof target !== 'object') continue;
              const refSnapshot = {
                component_name: target.$options?.name || target.$options?._componentTag || null,
                matched_keys: collectMatchedKeys(target),
                snapshot: snapshotObject(target),
                nested_snapshots: snapshotNestedMatches(target),
              };
              if (refKey === 'RTM_reportTable') {
                const propsData = target.$options?.propsData || {};
                refSnapshot.special_snapshot = {
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
                if ('allTableData' in target) {
                  refSnapshot.special_snapshot.allTableData = summarizeValue(target.allTableData);
                }
                if ('tableData' in target) {
                  refSnapshot.special_snapshot.tableData = summarizeValue(target.tableData);
                }
                if (target.vxeTable && typeof target.vxeTable === 'object') {
                  const vxe = target.vxeTable;
                  const database = vxe.database && typeof vxe.database === 'object'
                    ? Object.fromEntries(
                        Object.entries(vxe.database)
                          .slice(0, 20)
                          .map(([key, value]) => [key, summarizeValue(value)]),
                      )
                    : null;
                  refSnapshot.special_snapshot.vxeTable_snapshot = {
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
              }
              refsSnapshot[refKey] = refSnapshot;
            }
          }
          const route = vm?.$route || {};
          const parent = vm?.$parent || null;
          const root = vm?.$root || null;
          const storageSnapshot = {};
          for (const storage of [window.localStorage, window.sessionStorage]) {
            for (let i = 0; i < storage.length; i += 1) {
              const key = storage.key(i);
              if (!key) continue;
              if (!/(return|menu|grid|report|stock|type|search|query|condition|filter)/i.test(key)) continue;
              storageSnapshot[key] = storage.getItem(key);
            }
          }
          return {
            component_found: !!vm,
            component_name: vm?.$options?.name || vm?.$options?._componentTag || componentName,
            own_snapshot: snapshotObject(vm),
            parent_snapshot: snapshotObject(parent),
            root_snapshot: snapshotObject(root),
            route: {
              path: route.path || '',
              name: route.name || '',
              fullPath: route.fullPath || '',
              query: route.query || {},
              params: route.params || {},
            },
            refs: vm?.$refs ? Object.keys(vm.$refs).slice(0, 30) : [],
            refs_snapshot: refsSnapshot,
            safe_methods: safeMethodInfo,
            safe_method_sources: safeMethodSources,
            storage_snapshot: storageSnapshot,
          };
        }""",
        [component_name, list(fallback_method_names)],
    )


def _capture_component_store_state(frame, *, component_name: str) -> dict[str, Any]:
    return frame.evaluate(
        """([componentName, pattern]) => {
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
          const summarizeObjectByPattern = (target, patternText) => {
            if (!target || typeof target !== 'object') return {};
            const regex = new RegExp(patternText, 'i');
            const keys = Object.keys(target).filter((key) => regex.test(key)).slice(0, 40);
            return Object.fromEntries(keys.map((key) => [key, summarizeValue(target[key])]));
          };
          const store = vm?.$store || vm?.$root?.$store || null;
          const root = vm?.$root || null;
          return {
            component_found: !!vm,
            has_store: !!store,
            store_state_snapshot: summarizeObjectByPattern(store?.state, pattern),
            store_getter_keys: store?.getters ? Object.keys(store.getters).filter((key) => new RegExp(pattern, 'i').test(key)).slice(0, 40) : [],
            root_snapshot: summarizeObjectByPattern(root, pattern),
            root_data_snapshot: summarizeObjectByPattern(root?._data, pattern),
          };
        }""",
        [component_name, CONTEXT_FIELD_PATTERN],
    )


def _capture_component_global_storage_state(frame, *, component_name: str) -> dict[str, Any]:
    return frame.evaluate(
        """([componentName, patternText]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          const pattern = new RegExp(patternText, 'i');

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
        [component_name, CONTEXT_FIELD_PATTERN],
    )


def _capture_component_injection_context(frame, *, component_name: str) -> dict[str, Any]:
    return frame.evaluate(
        """([componentName, patternText]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          const pattern = new RegExp(patternText, 'i');

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

          const summarizeVmFields = (target) => {
            if (!target || typeof target !== 'object') return {};
            const keys = Object.keys(target).filter((key) => !key.startsWith('_') && pattern.test(key)).slice(0, 40);
            return Object.fromEntries(keys.map((key) => [key, summarizeValue(target[key])]));
          };

          if (!vm) return { component_found: false };

          const parent = vm.$parent || null;
          const root = vm.$root || null;
          const rootData = root?._data || {};
          return {
            component_found: true,
            route_snapshot: summarizeRoute(vm.$route || root?.$route || null),
            vm_fields_snapshot: summarizeVmFields(vm),
            parent_fields_snapshot: summarizeVmFields(parent),
            root_data_fields_snapshot: summarizeVmFields(rootData),
          };
        }""",
        [component_name, CONTEXT_FIELD_PATTERN],
    )


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
    reference_payloads: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    collector.set_action(f"component_method_{method_name}")
    counts = collector.snapshot_counts()
    local_state_before = _capture_page_component_state(
        frame,
        component_name=component_name,
        fallback_method_names=(method_name,),
    )
    invocation = frame.evaluate(
        """async ([componentName, methodName]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          let hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          if (!hit) {
            hit = nodes.find((node) => typeof node.__vue__?.[methodName] === 'function') || null;
          }
          const vm = hit?.__vue__ || null;
          if (!vm) {
            return { component_found: false, method_found: false, invoked: false };
          }
          const method = vm[methodName];
          if (typeof method !== 'function') {
            return { component_found: true, method_found: false, invoked: false };
          }
          try {
            let result = method.call(vm);
            if (result && typeof result.then === 'function') {
              result = await result;
            }
            return {
              component_found: true,
              method_found: true,
              invoked: true,
              result_type: Array.isArray(result) ? 'array' : typeof result,
              result_preview: Array.isArray(result) ? result.slice(0, 2) : result,
            };
          } catch (error) {
            return {
              component_found: true,
              method_found: true,
              invoked: false,
              error: String(error),
            };
          }
        }""",
        [component_name, method_name],
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
        **build_step_delta(delta, previous_requests, reference_payloads=reference_payloads),
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
        "component_diagnostics": _capture_filter_component_diagnostics(frame),
        "local_state_after": _capture_page_component_state(
            frame,
            component_name=component_name,
            fallback_method_names=(method_name,),
        ),
        "component_ancestry_after": _capture_component_ancestry(
            frame,
            component_name=component_name,
        ),
    }
    return step, previous_requests + delta.get("requests", [])


def _capture_ref_indexeddb_state(
    frame,
    *,
    component_name: str,
    ref_name: str,
) -> dict[str, Any]:
    return frame.evaluate(
        """async ([componentName, refName]) => {
          const nodes = Array.from(document.querySelectorAll('*'));
          const hit = nodes.find((node) => (node.__vue__?.$options?.name || '') === componentName);
          const vm = hit?.__vue__ || null;
          if (!vm) return { component_found: false };

          const raw = vm.$refs?.[refName];
          const target = Array.isArray(raw) ? raw[0] : raw;
          if (!target || typeof target !== 'object') {
            return { component_found: true, ref_found: false };
          }

          const databaseTableName = target.$options?.propsData?.databaseTableName || null;
          const databaseName = target?.vxeTable?.database?.DateBaseName || null;
          const version = target?.vxeTable?.database?.Version || null;
          const summarize = (value) => {
            if (value === null || value === undefined) return null;
            if (Array.isArray(value)) return { type: 'array', length: value.length, sample: value.slice(0, 5) };
            if (typeof value === 'object') return { type: 'object', keys: Object.keys(value).slice(0, 20) };
            return value;
          };

          const response = {
            component_found: true,
            ref_found: true,
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
            browser_db_meta: summarize(target?.vxeTable?.database),
          };
          db.close();
          return response;
        }""",
        [component_name, ref_name],
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


def _latest_endpoint_request(delta: dict[str, list[dict[str, Any]]], endpoint: str) -> dict[str, Any] | None:
    for request in reversed(delta.get("requests", [])):
        if extract_endpoint_name(str(request.get("url") or "")) == endpoint:
            return request
    return None


def _latest_endpoint_response(delta: dict[str, list[dict[str, Any]]], endpoint: str) -> dict[str, Any] | None:
    for response in reversed(delta.get("responses", [])):
        if extract_endpoint_name(str(response.get("url") or "")) == endpoint:
            return response
    return None


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
    reference_payloads: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    component_name: str | None = None,
    fallback_method_names: tuple[str, ...] = (),
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
        **build_step_delta(delta, previous_requests, reference_payloads=reference_payloads),
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
        "component_diagnostics": _capture_filter_component_diagnostics(frame),
    }
    if component_name:
        step["page_component_state_after"] = _capture_page_component_state(
            frame,
            component_name=component_name,
            fallback_method_names=fallback_method_names,
        )
    if metadata:
        step.update(metadata)
    return step, previous_requests + delta.get("requests", [])


def main() -> int:
    parser = argparse.ArgumentParser(description="对 Yeusoft 退货明细页面做 UI 维度取证，抓取筛选动作后的真实请求体")
    parser.add_argument("--site-url", default="https://jypos.yeusoft.net/")
    parser.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--analysis-root", default=str(PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--wait-ms", type=int, default=NETWORK_WAIT_MS)
    args = parser.parse_args()

    sync_playwright, _ = import_playwright()
    entry = _resolve_page_entry("退货明细", Path(args.analysis_root))

    run_dir = Path(args.output_root) / f"{now_local().strftime('%Y%m%d-%H%M%S')}-return-detail-ui-probe"
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
                raise RuntimeError("未在菜单树中找到退货明细")

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
                    "probes": [],
                    "ref_method_sources": [],
                }

                baseline_step, previous_requests = _run_probe_action(
                    page=page,
                    frame=frame,
                    collector=collector,
                    action_key="open_return_detail",
                    callback=lambda: bool(open_report_by_menu_item(frame, page, menu_item) or True),
                    wait_ms=args.wait_ms,
                    previous_requests=previous_requests,
                    scope_texts=scope_texts,
                    scope_action_texts=scope_action_texts,
                    component_name=PAGE_COMPONENT_NAME,
                    fallback_method_names=SAFE_COMPONENT_METHODS,
                )
                result["baseline"]["open_step"] = baseline_step
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
                    component_name=PAGE_COMPONENT_NAME,
                )
                result["baseline"]["component_diagnostics_after_open"] = _capture_filter_component_diagnostics(frame)
                result["baseline"]["visible_controls_after_open"] = capture_visible_controls(
                    frame,
                    scope_texts=scope_texts,
                    action_texts=scope_action_texts,
                )

                baseline_query_step, previous_requests = _run_probe_action(
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
                    component_name=PAGE_COMPONENT_NAME,
                    fallback_method_names=SAFE_COMPONENT_METHODS,
                )
                baseline_request = _latest_endpoint_request({"requests": previous_requests, "responses": collector.responses}, "SelReturnStockList")
                baseline_response = _latest_endpoint_response({"requests": collector.requests, "responses": collector.responses}, "SelReturnStockList")
                result["baseline"]["query_step"] = baseline_query_step
                result["baseline"]["return_detail_post_data"] = baseline_request.get("post_data") if baseline_request else None
                result["baseline"]["return_detail_response"] = baseline_response
                result["baseline"]["component_state_after_query"] = capture_component_state(
                    frame,
                    scope_texts=scope_texts,
                    action_texts=scope_action_texts,
                )
                result["baseline"]["method_owner_candidates_after_query"] = _discover_method_owner_candidates(
                    frame,
                    method_names=SAFE_COMPONENT_METHODS,
                )
                result["baseline"]["page_component_state_after_query"] = _capture_page_component_state(
                    frame,
                    component_name=PAGE_COMPONENT_NAME,
                    fallback_method_names=SAFE_COMPONENT_METHODS,
                )
                result["baseline"]["component_ancestry_after_query"] = _capture_component_ancestry(
                    frame,
                    component_name=PAGE_COMPONENT_NAME,
                )
                result["baseline"]["component_ancestry_ref_states_after_query"] = [
                    _capture_ancestry_ref_state(
                        frame,
                        component_name=PAGE_COMPONENT_NAME,
                        depth=depth,
                        ref_name=ref_name,
                    )
                    for depth, ref_name in ANCESTRY_REF_PROBES
                ]
                result["baseline"]["component_ancestry_method_sources_after_query"] = _capture_ancestry_method_sources(
                    frame,
                    component_name=PAGE_COMPONENT_NAME,
                )
                result["baseline"]["component_store_state_after_query"] = _capture_component_store_state(
                    frame,
                    component_name=PAGE_COMPONENT_NAME,
                )
                result["baseline"]["component_global_storage_after_query"] = _capture_component_global_storage_state(
                    frame,
                    component_name=PAGE_COMPONENT_NAME,
                )
                result["baseline"]["component_injection_context_after_query"] = _capture_component_injection_context(
                    frame,
                    component_name=PAGE_COMPONENT_NAME,
                )
                result["baseline"]["table_ref_indexeddb_after_query"] = _capture_ref_indexeddb_state(
                    frame,
                    component_name=PAGE_COMPONENT_NAME,
                    ref_name=TABLE_REF_NAME,
                )
                result["baseline"]["component_diagnostics_after_query"] = _capture_filter_component_diagnostics(frame)
                result["baseline"]["visible_controls_after_query"] = capture_visible_controls(
                    frame,
                    scope_texts=scope_texts,
                    action_texts=scope_action_texts,
                )

                reference_payloads = {}
                if baseline_request and baseline_request.get("post_data") is not None:
                    reference_payloads["SelReturnStockList"] = baseline_request["post_data"]

                for label, option_text in FILTER_OPTION_TEXTS:
                    click_clear_step, previous_requests = _run_probe_action(
                        page=page,
                        frame=frame,
                        collector=collector,
                        action_key=f"clear_before_{label}",
                        callback=lambda: click_exact_text(
                            frame,
                            "清空",
                            scope_texts=scope_texts,
                            action_texts=scope_action_texts,
                        ),
                        wait_ms=1000,
                        previous_requests=previous_requests,
                        scope_texts=scope_texts,
                        scope_action_texts=scope_action_texts,
                        component_name=PAGE_COMPONENT_NAME,
                        fallback_method_names=SAFE_COMPONENT_METHODS,
                    )
                    select_step, previous_requests = _run_probe_action(
                        page=page,
                        frame=frame,
                        collector=collector,
                        action_key=f"select_{label}",
                        callback=lambda option_text=option_text: click_exact_text(
                            frame,
                            option_text,
                            scope_texts=scope_texts,
                            action_texts=scope_action_texts,
                        ),
                        wait_ms=1000,
                        previous_requests=previous_requests,
                        scope_texts=scope_texts,
                        scope_action_texts=scope_action_texts,
                        component_name=PAGE_COMPONENT_NAME,
                        fallback_method_names=SAFE_COMPONENT_METHODS,
                    )
                    query_step, previous_requests = _run_probe_action(
                        page=page,
                        frame=frame,
                        collector=collector,
                        action_key=f"query_after_{label}",
                        callback=lambda: click_query_button(
                            frame,
                            scope_texts=scope_texts,
                            action_texts=scope_action_texts,
                        ),
                        wait_ms=args.wait_ms,
                        previous_requests=previous_requests,
                        scope_texts=scope_texts,
                        scope_action_texts=scope_action_texts,
                        reference_payloads=reference_payloads,
                        metadata={"filter_label": label, "filter_option_text": option_text},
                        component_name=PAGE_COMPONENT_NAME,
                        fallback_method_names=SAFE_COMPONENT_METHODS,
                    )
                    latest_request = _latest_endpoint_request(
                        {"requests": collector.requests, "responses": collector.responses},
                        "SelReturnStockList",
                    )
                    latest_response = _latest_endpoint_response(
                        {"requests": collector.requests, "responses": collector.responses},
                        "SelReturnStockList",
                    )
                    probe_result = {
                        "label": label,
                        "option_text": option_text,
                        "clear_step": click_clear_step,
                        "select_step": select_step,
                        "query_step": query_step,
                        "return_detail_post_data": latest_request.get("post_data") if latest_request else None,
                        "return_detail_response": latest_response,
                    }
                    result["probes"].append(probe_result)

                for method_name in SAFE_COMPONENT_METHODS:
                    method_step, previous_requests = _run_component_method_probe(
                        page=page,
                        frame=frame,
                        collector=collector,
                        component_name=PAGE_COMPONENT_NAME,
                        method_name=method_name,
                        wait_ms=args.wait_ms,
                        previous_requests=previous_requests,
                        scope_texts=scope_texts,
                        scope_action_texts=scope_action_texts,
                        reference_payloads=reference_payloads,
                    )
                    result["probes"].append(
                        {
                            "label": f"component_method:{method_name}",
                            "component_method_step": method_step,
                        }
                    )

                result["ref_method_sources"].append(
                    _capture_ref_method_sources(
                        frame,
                        component_name=PAGE_COMPONENT_NAME,
                        ref_name=TABLE_REF_NAME,
                        method_names=TABLE_REF_METHOD_SOURCE_NAMES,
                    )
                )

                safe_json_dump(page_dir / "manifest.json", result)
                analysis_path = Path(args.analysis_root) / f"return-detail-ui-probe-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
                safe_json_dump(analysis_path, result)
                print(json.dumps({"ok": True, "output": str(analysis_path)}, ensure_ascii=False))
            finally:
                collector.close()
        finally:
            context.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
