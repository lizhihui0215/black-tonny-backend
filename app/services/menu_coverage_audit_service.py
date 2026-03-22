from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from app.services.yeusoft_page_research_service import (
    ResearchPageRegistryEntry,
    flatten_menu,
    list_menu_items,
)


def _path_tuple(parts: Sequence[str] | None) -> tuple[str, ...]:
    return tuple(str(part).strip() for part in (parts or []) if str(part).strip())


def _page_summary_lookup(pages: Sequence[Mapping[str, Any]] | None) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for page in pages or []:
        title = str(page.get("title") or page.get("page", {}).get("title") or "").strip()
        if title and title not in lookup:
            lookup[title] = dict(page)
    return lookup


def _registry_indices(
    registry: Sequence[ResearchPageRegistryEntry],
) -> tuple[dict[tuple[str, ...], list[ResearchPageRegistryEntry]], dict[tuple[str, str], list[ResearchPageRegistryEntry]]]:
    by_path: dict[tuple[str, ...], list[ResearchPageRegistryEntry]] = defaultdict(list)
    by_title: dict[tuple[str, str], list[ResearchPageRegistryEntry]] = defaultdict(list)
    for entry in registry:
        by_path[_path_tuple(entry.target_menu_path)].append(entry)
        by_title[(str(entry.menu_root_name).strip(), str(entry.menu_target_title).strip())].append(entry)
    return by_path, by_title


def match_registry_entries(
    menu_item: Mapping[str, Any],
    registry: Sequence[ResearchPageRegistryEntry],
) -> list[ResearchPageRegistryEntry]:
    by_path, by_title = _registry_indices(registry)
    menu_path = _path_tuple(menu_item.get("menuPath") or [])
    root_name = str(menu_item.get("rootName") or "").strip()
    func_name = str(menu_item.get("FuncName") or "").strip()
    matches = list(by_path.get(menu_path, []))
    if matches:
        return matches
    return list(by_title.get((root_name, func_name), []))


def infer_domain_from_menu_metadata(root_name: str, group_name: str, title: str) -> tuple[str, str]:
    joined = " ".join(filter(None, [root_name, group_name, title]))
    if any(token in joined for token in ("库存", "进销", "出入库", "进出")):
        return ("inventory", "库存")
    if "储值" in joined:
        return ("stored_value", "储值")
    if root_name == "会员资料" or "会员" in joined or "VIP" in joined.upper():
        return ("member", "会员")
    if any(token in joined for token in ("流水", "对账", "支付", "单据")):
        return ("payment_and_docs", "流水单据")
    return ("sales", "销售")


def _container_nodes(menu_list: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    containers: list[dict[str, Any]] = []
    for item in flatten_menu(menu_list):
        func_name = str(item.get("FuncName") or item.get("Name") or "").strip()
        func_url = str(item.get("FuncUrl") or "").strip()
        parents = _path_tuple(item.get("_parents") or [])
        if not func_name or not parents or func_url:
            continue
        containers.append(
            {
                "title": func_name,
                "menu_path": list(parents + (func_name,)),
                "root_name": parents[0] if parents else "",
                "group_name": parents[1] if len(parents) > 1 else "",
                "coverage_status": "container_only",
            }
        )
    return containers


def classify_menu_page_record(
    *,
    menu_item: Mapping[str, Any],
    open_status: str,
    error: str | None,
    registry_matches: Sequence[ResearchPageRegistryEntry],
    latest_page_summary: Mapping[str, dict[str, Any]],
    candidate_endpoints: Sequence[str],
    candidate_data_endpoints: Sequence[str],
    visible_control_count: int,
) -> dict[str, Any]:
    root_name = str(menu_item.get("rootName") or "").strip()
    group_name = str(menu_item.get("groupName") or "").strip()
    title = str(menu_item.get("FuncName") or "").strip()
    menu_path = _path_tuple(menu_item.get("menuPath") or [])

    matched_titles = [entry.title for entry in registry_matches]
    matched_target_paths = [list(entry.target_menu_path) for entry in registry_matches]
    matched_page_research_titles = [
        entry.title for entry in registry_matches if entry.title in latest_page_summary
    ]
    direct_page_research = latest_page_summary.get(title) or {}
    if not matched_page_research_titles and direct_page_research:
        matched_page_research_titles = [title]
    latest_endpoint_candidates: list[str] = []
    latest_data_endpoint_candidates: list[str] = []
    for research_title in matched_page_research_titles:
        summary = latest_page_summary.get(research_title) or {}
        for item in summary.get("endpoint_summaries") or []:
            endpoint = str(item.get("endpoint") or "").strip()
            if not endpoint:
                continue
            latest_endpoint_candidates.append(endpoint)
            if item.get("is_data_endpoint"):
                latest_data_endpoint_candidates.append(endpoint)
    merged_candidate_endpoints = list(
        dict.fromkeys(list(candidate_endpoints) + latest_endpoint_candidates)
    )
    merged_candidate_data_endpoints = list(
        dict.fromkeys(list(candidate_data_endpoints) + latest_data_endpoint_candidates)
    )

    if registry_matches or direct_page_research:
        if open_status == "opened":
            coverage_status = "covered"
            coverage_confidence = (
                "high"
                if any(_path_tuple(entry.target_menu_path) == menu_path for entry in registry_matches)
                or (
                    direct_page_research
                    and _path_tuple(direct_page_research.get("target_menu_path") or []) == menu_path
                )
                else "medium"
            )
        else:
            coverage_status = "visible_but_failed"
            coverage_confidence = "medium"
    else:
        if open_status == "opened":
            coverage_status = "visible_but_untracked"
            coverage_confidence = "medium"
        else:
            coverage_status = "visible_but_failed"
            coverage_confidence = "low"

    return {
        "title": title,
        "page_title": title,
        "menu_path": list(menu_path),
        "root_name": root_name,
        "group_name": group_name,
        "route_or_url": str(menu_item.get("FuncUrl") or ""),
        "open_status": open_status,
        "error": error,
        "coverage_status": coverage_status,
        "coverage_confidence": coverage_confidence,
        "matched_registry_titles": matched_titles,
        "matched_target_menu_paths": matched_target_paths,
        "matched_page_research_titles": matched_page_research_titles,
        "candidate_endpoints": merged_candidate_endpoints,
        "candidate_data_endpoints": merged_candidate_data_endpoints,
        "visible_control_count": visible_control_count,
    }


def build_menu_coverage_audit(
    *,
    menu_list: Sequence[Mapping[str, Any]],
    registry: Sequence[ResearchPageRegistryEntry],
    audited_pages: Sequence[Mapping[str, Any]],
    latest_page_research_pages: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    page_summary_lookup = _page_summary_lookup(latest_page_research_pages)
    clickable_items = list_menu_items(menu_list)
    clickable_by_path = {_path_tuple(item.get("menuPath") or []): item for item in clickable_items}
    audited_by_path = {
        _path_tuple(item.get("menu_path") or []): item
        for item in audited_pages
        if item.get("menu_path")
    }

    page_records: list[dict[str, Any]] = []
    for item in clickable_items:
        path_key = _path_tuple(item.get("menuPath") or [])
        audited = audited_by_path.get(path_key, {})
        registry_matches = match_registry_entries(item, registry)
        page_records.append(
            classify_menu_page_record(
                menu_item=item,
                open_status=str(audited.get("open_status") or "missing"),
                error=audited.get("error"),
                registry_matches=registry_matches,
                latest_page_summary=page_summary_lookup,
                candidate_endpoints=audited.get("candidate_endpoints") or [],
                candidate_data_endpoints=audited.get("candidate_data_endpoints") or [],
                visible_control_count=int(audited.get("visible_control_count") or 0),
            )
        )

    covered = [item for item in page_records if item["coverage_status"] == "covered"]
    unknown_pages = [item for item in page_records if item["coverage_status"] == "visible_but_untracked"]
    failed_pages = [item for item in page_records if item["coverage_status"] == "visible_but_failed"]
    containers = _container_nodes(menu_list)

    unmatched_registry_targets = [
        {
            "title": entry.title,
            "menu_target_title": entry.menu_target_title,
            "menu_root_name": entry.menu_root_name,
            "target_menu_path": list(entry.target_menu_path),
        }
        for entry in registry
        if _path_tuple(entry.target_menu_path) not in clickable_by_path
    ]

    summary = {
        "menu_node_count": len(flatten_menu(menu_list)),
        "container_only_count": len(containers),
        "clickable_page_count": len(clickable_items),
        "covered_count": len(covered),
        "visible_but_untracked_count": len(unknown_pages),
        "visible_but_failed_count": len(failed_pages),
        "classified_visible_count": len(page_records),
        "unclassified_count": max(0, len(clickable_items) - len(page_records)),
        "audit_complete": len(page_records) == len(clickable_items),
        "all_visible_pages_classified": len(page_records) == len(clickable_items),
        "unknown_pages": [
            {
                "title": item["title"],
                "menu_path": item["menu_path"],
                "root_name": item["root_name"],
                "group_name": item["group_name"],
            }
            for item in unknown_pages
        ],
        "unmatched_registry_targets": unmatched_registry_targets,
    }

    return {
        "summary": summary,
        "pages": page_records,
        "containers": containers,
    }


def load_latest_menu_coverage_audit(analysis_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    candidates = sorted(analysis_root.glob("menu-coverage-audit-*.json"))
    if not candidates:
        return None, None
    path = candidates[-1]
    return path, json.loads(path.read_text("utf-8"))
