from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.services.erp_research_service import (
    DATE_FIELD_HINTS,
    DIY_CONTEXT_HINTS,
    ENUM_FIELD_HINTS,
    ORG_FIELD_HINTS,
    PAGINATION_FIELD_HINTS,
    SEARCH_FIELD_HINTS,
    analyze_response_payload,
    parse_report_specs,
    slugify,
)


REPORT_ROOT_NAME = "报表管理"
INTERACTIVE_TEXT_SELECTOR = (
    "a, button, li, p, span, div, .el-menu-item, .el-submenu__title, .ivu-menu-item, .menu-item"
)
REPORT_ALIAS_MAP = {
    "销售明细统计": "零售明细统计",
    "导购员统计": "导购员报表",
}
RESEARCH_PAGE_OVERRIDES: dict[str, dict[str, str]] = {
    "库存总和分析-按年份季节": {
        "menu_target_title": "库存综合分析",
        "menu_root_name": REPORT_ROOT_NAME,
        "group_name": "库存报表",
        "variant_label": "按年份季节",
        "variant_of": "库存综合分析",
    },
    "库存总和分析-按中分类": {
        "menu_target_title": "库存综合分析",
        "menu_root_name": REPORT_ROOT_NAME,
        "group_name": "库存报表",
        "variant_label": "按中分类",
        "variant_of": "库存综合分析",
    },
    "库存总和分析-按波段": {
        "menu_target_title": "库存综合分析",
        "menu_root_name": REPORT_ROOT_NAME,
        "group_name": "库存报表",
        "variant_label": "按波段分析",
        "variant_of": "库存综合分析",
    },
    "库存综合分析-按年份季节": {
        "menu_target_title": "库存综合分析",
        "menu_root_name": REPORT_ROOT_NAME,
        "group_name": "库存报表",
        "variant_label": "按年份季节",
        "variant_of": "库存综合分析",
    },
    "库存综合分析-按中分类": {
        "menu_target_title": "库存综合分析",
        "menu_root_name": REPORT_ROOT_NAME,
        "group_name": "库存报表",
        "variant_label": "按中分类",
        "variant_of": "库存综合分析",
    },
    "库存综合分析-按波段分析": {
        "menu_target_title": "库存综合分析",
        "menu_root_name": REPORT_ROOT_NAME,
        "group_name": "库存报表",
        "variant_label": "按波段分析",
        "variant_of": "库存综合分析",
    },
    "会员总和分析": {
        "menu_target_title": "会员综合分析",
        "menu_root_name": REPORT_ROOT_NAME,
        "group_name": "会员报表",
        "variant_of": "会员综合分析",
    },
    "会员消费排行榜": {
        "menu_target_title": "会员消费排行",
        "menu_root_name": REPORT_ROOT_NAME,
        "group_name": "会员报表",
        "variant_of": "会员消费排行",
    },
    "会员中心": {
        "menu_target_title": "会员中心",
        "menu_root_name": "会员资料",
        "group_name": "",
    },
}
REPORT_GROUP_MAP = {
    "零售明细统计": "零售报表",
    "销售明细统计": "零售报表",
    "导购员报表": "零售报表",
    "导购员统计": "零售报表",
    "店铺零售清单": "零售报表",
    "销售清单": "零售报表",
    "库存明细统计": "库存报表",
    "库存零售统计": "库存报表",
    "库存综合分析-按年份季节": "库存报表",
    "库存综合分析-按中分类": "库存报表",
    "库存综合分析-按波段分析": "库存报表",
    "库存多维分析": "库存报表",
    "进销存统计": "进出报表",
    "出入库单据": "进出报表",
    "日进销存": "进出报表",
    "会员总和分析": "会员报表",
    "会员消费排行": "会员报表",
    "储值按店汇总": "会员报表",
    "储值卡汇总": "会员报表",
    "储值卡明细": "会员报表",
    "会员中心": "会员报表",
    "商品销售情况": "综合分析",
    "商品品类分析": "综合分析",
    "门店销售月报": "综合分析",
    "每日流水单": "对账报表",
}
INTERESTING_ENDPOINTS = (
    "GetMenuList",
    "GetConfiguration",
    "GetFilterContentData",
    "GetControlData",
    "GetViewGridList",
    "GetDIYReportData",
    "SelDeptSaleList",
    "SelPersonSale",
    "SelDeptStockWaitList",
    "SelDeptStockSaleList",
    "SelStockAnalysisList",
    "SelDeptStockAnalysis",
    "SelInSalesReport",
    "SelOutInStockReport",
    "SelInSalesReportByDay",
    "SelVipAnalysisReport",
    "SelVipSaleRank",
    "SelDeptList",
    "SelWareList",
    "SelWareInfoList",
    "SelSaleReport",
    "SelSaleReportData",
    "SelWareTypeAnalysisList",
    "DeptMonthSalesReport",
    "SelectRetailDocPaymentSlip",
    "ReturnStockBaseInfo",
    "SelReturnStockList",
)
NON_DATA_ENDPOINTS = {
    "GetMenuList",
    "GetConfiguration",
    "GetFilterContentData",
    "GetControlData",
    "GetViewGridList",
    "ReturnStockBaseInfo",
}
DEFAULT_QUERY_DATE_RANGE = {
    "start": "2025-03-01",
    "end": "2026-04-01",
}
SALES_DOCUMENT_ROUTE_URL = "https://erpapistaging.yeusoft.net/eposapi/YisEposReport/SelSaleReport"
SALES_DOCUMENT_ROUTE_PAYLOAD = {
    "edate": "20260401",
    "bdate": "20250301",
    "saletype": "0",
    "type": "0",
    "val": "",
    "page": 1,
    "pagesize": 999999,
    "isshow": "1",
}
SECOND_ROUND_PROBE_TARGETS: dict[str, tuple[str, ...]] = {
    "sales_inventory": (
        "销售清单",
        "零售明细统计",
        "库存明细统计",
        "出入库单据",
        "库存总和分析-按年份季节",
        "库存总和分析-按中分类",
        "库存总和分析-按波段",
        "库存综合分析-按年份季节",
        "库存综合分析-按中分类",
        "库存综合分析-按波段分析",
    ),
}


@dataclass(frozen=True)
class ResearchStepRecipe:
    key: str
    label: str
    kind: str
    target_text: str | None = None
    wait_ms: int = 2500


@dataclass(frozen=True)
class ResearchPageRecipe:
    query_required: bool = True
    date_range_applicable: bool = True
    variant_labels: tuple[str, ...] = ()
    steps: tuple[ResearchStepRecipe, ...] = ()


@dataclass(frozen=True)
class ResearchPageRegistryEntry:
    title: str
    canonical_name: str
    slug: str
    menu_target_title: str
    menu_root_name: str
    group_name: str
    menu_path: tuple[str, ...]
    target_menu_path: tuple[str, ...]
    sample_url: str | None
    sample_payload: dict[str, Any] | list[Any] | str | None
    image_evidence_count: int
    variant_label: str | None
    variant_of: str | None
    recipe: ResearchPageRecipe

    def as_dict(self) -> dict[str, Any]:
        payload_type = None
        if self.sample_payload is not None:
            payload_type = type(self.sample_payload).__name__
        return {
            "title": self.title,
            "canonical_name": self.canonical_name,
            "slug": self.slug,
            "menu_target_title": self.menu_target_title,
            "menu_root_name": self.menu_root_name,
            "group_name": self.group_name,
            "menu_path": list(self.menu_path),
            "target_menu_path": list(self.target_menu_path),
            "sample_url": self.sample_url,
            "sample_payload_type": payload_type,
            "image_evidence_count": self.image_evidence_count,
            "variant_label": self.variant_label,
            "variant_of": self.variant_of,
            "is_alias_or_variant": self.title != self.menu_target_title or bool(self.variant_label),
            "recipe": asdict(self.recipe),
        }


@dataclass(frozen=True)
class SingleVariableProbeCase:
    key: str
    label: str
    url: str
    payload: dict[str, Any]
    parameter_path: str
    parameter_value: Any
    category: str
    reference_payload: dict[str, Any] | None = None
    notes: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "url": self.url,
            "payload": self.payload,
            "parameter_path": self.parameter_path,
            "parameter_value": self.parameter_value,
            "category": self.category,
            "reference_payload": self.reference_payload,
            "notes": self.notes,
        }


def normalize_report_name(report_name: str) -> str:
    return REPORT_ALIAS_MAP.get(report_name, report_name)


def _strip_image_suffix(name: str) -> str:
    return re.sub(r"-\d+$", "", name.strip())


def _collect_image_evidence_counts(api_images_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    if not api_images_dir.exists():
        return {}
    for image_path in api_images_dir.glob("*.png"):
        base_name = _strip_image_suffix(image_path.stem)
        if base_name:
            counts[normalize_report_name(base_name)] += 1
    return dict(counts)


def build_default_page_recipe(title: str) -> ResearchPageRecipe:
    canonical = normalize_report_name(title)
    variant_labels: tuple[str, ...] = ()
    date_range_applicable = canonical not in {"会员中心"}

    if canonical == "销售清单":
        variant_labels = ("按单据", "按明细")
    elif canonical == "库存明细统计":
        variant_labels = ("库存", "销售", "全部")
    elif canonical == "出入库单据":
        variant_labels = ("按日期", "按单据日期")

    steps = (
        ResearchStepRecipe(key="open", label="打开页面", kind="open", wait_ms=2500),
        ResearchStepRecipe(key="query", label="执行查询", kind="query", wait_ms=3500),
    )
    return ResearchPageRecipe(
        query_required=True,
        date_range_applicable=date_range_applicable,
        variant_labels=variant_labels,
        steps=steps,
    )


def build_page_research_registry(report_doc_path: Path, api_images_dir: Path) -> list[ResearchPageRegistryEntry]:
    specs = parse_report_specs(report_doc_path)
    specs_by_title = {
        normalize_report_name(spec["title"]): spec
        for spec in specs
    }
    image_counts = _collect_image_evidence_counts(api_images_dir)
    ordered_titles: list[str] = []
    seen: set[str] = set()

    for spec in specs:
        canonical = normalize_report_name(spec["title"])
        if canonical not in seen:
            ordered_titles.append(canonical)
            seen.add(canonical)

    for title in sorted(image_counts):
        if title not in seen:
            ordered_titles.append(title)
            seen.add(title)

    registry: list[ResearchPageRegistryEntry] = []
    for title in ordered_titles:
        spec = specs_by_title.get(title)
        override = RESEARCH_PAGE_OVERRIDES.get(title, {})
        menu_target_title = override.get("menu_target_title", title)
        menu_root_name = override.get("menu_root_name", REPORT_ROOT_NAME)
        group_name = override.get("group_name", REPORT_GROUP_MAP.get(title, REPORT_GROUP_MAP.get(menu_target_title, "")))
        variant_label = override.get("variant_label")
        variant_of = override.get("variant_of")
        menu_path = tuple(part for part in (menu_root_name, group_name, title) if part)
        target_menu_path = tuple(part for part in (menu_root_name, group_name, menu_target_title) if part)
        recipe = build_default_page_recipe(title)
        if variant_label:
            recipe = ResearchPageRecipe(
                query_required=recipe.query_required,
                date_range_applicable=recipe.date_range_applicable,
                variant_labels=(variant_label,),
                steps=recipe.steps,
            )
        registry.append(
            ResearchPageRegistryEntry(
                title=title,
                canonical_name=title,
                slug=slugify(title),
                menu_target_title=menu_target_title,
                menu_root_name=menu_root_name,
                group_name=group_name,
                menu_path=menu_path,
                target_menu_path=target_menu_path,
                sample_url=spec["url"] if spec else None,
                sample_payload=spec["payload"] if spec else None,
                image_evidence_count=image_counts.get(title, 0),
                variant_label=variant_label,
                variant_of=variant_of,
                recipe=recipe,
            )
        )
    return registry


def build_unknown_page_registry_entries(
    menu_coverage_payload: Mapping[str, Any] | None,
    *,
    existing_registry: Sequence[ResearchPageRegistryEntry] = (),
) -> list[ResearchPageRegistryEntry]:
    return build_menu_coverage_registry_entries(
        menu_coverage_payload,
        existing_registry=existing_registry,
        coverage_statuses={"visible_but_untracked"},
    )


def build_menu_coverage_registry_entries(
    menu_coverage_payload: Mapping[str, Any] | None,
    *,
    existing_registry: Sequence[ResearchPageRegistryEntry] = (),
    only_titles: Sequence[str] | None = None,
    coverage_statuses: set[str] | None = None,
) -> list[ResearchPageRegistryEntry]:
    if not menu_coverage_payload:
        return []

    known_titles = {entry.title for entry in existing_registry}
    wanted = {str(title).strip() for title in (only_titles or []) if str(title).strip()}
    entries: list[ResearchPageRegistryEntry] = []
    for page in menu_coverage_payload.get("pages", []):
        coverage_status = str(page.get("coverage_status") or "")
        if coverage_statuses is not None and coverage_status not in coverage_statuses:
            continue
        title = str(page.get("title") or "").strip()
        if wanted and title not in wanted:
            continue
        if not title or title in known_titles:
            continue
        root_name = str(page.get("root_name") or "").strip()
        group_name = str(page.get("group_name") or "").strip()
        menu_path = tuple(str(part).strip() for part in page.get("menu_path") or [] if str(part).strip())
        if not menu_path:
            menu_path = tuple(part for part in (root_name, group_name, title) if part)
        recipe = build_default_page_recipe(title)
        entries.append(
            ResearchPageRegistryEntry(
                title=title,
                canonical_name=title,
                slug=slugify(title),
                menu_target_title=title,
                menu_root_name=root_name,
                group_name=group_name,
                menu_path=menu_path,
                target_menu_path=menu_path,
                sample_url=None,
                sample_payload=None,
                image_evidence_count=0,
                variant_label=None,
                variant_of=None,
                recipe=recipe,
            )
        )
        known_titles.add(title)
    return entries


def flatten_menu(menu_list: Sequence[Mapping[str, Any]], parents: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for item in menu_list:
        if not isinstance(item, Mapping):
            continue
        func_name = str(item.get("FuncName") or item.get("Name") or "").strip()
        current_parents = parents + ((func_name,) if func_name else ())
        copied = dict(item)
        copied["_parents"] = list(parents)
        flattened.append(copied)
        children = (
            item.get("SubList")
            or item.get("Children")
            or item.get("children")
            or item.get("Items")
            or []
        )
        if isinstance(children, Sequence) and not isinstance(children, (str, bytes)):
            flattened.extend(flatten_menu(children, current_parents))
    return flattened
    flattened: list[dict[str, Any]] = []
    for item in menu_list:
        if not isinstance(item, Mapping):
            continue
        func_name = str(item.get("FuncName") or item.get("Name") or "").strip()
        current_parents = parents + ((func_name,) if func_name else ())
        copied = dict(item)
        copied["_parents"] = list(parents)
        flattened.append(copied)
        children = (
            item.get("SubList")
            or item.get("Children")
            or item.get("children")
            or item.get("Items")
            or []
        )
        if isinstance(children, Sequence) and not isinstance(children, (str, bytes)):
            flattened.extend(flatten_menu(children, current_parents))
    return flattened


def list_menu_items(menu_list: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in flatten_menu(menu_list):
        func_lid = str(item.get("FuncLID") or "")
        func_name = str(item.get("FuncName") or "").strip()
        func_url = str(item.get("FuncUrl") or "").strip()
        if not func_name or not func_url:
            continue
        parents = item.get("_parents") or []
        if not parents:
            continue
        root_name = str(parents[0]).strip()
        group_name = str(parents[1]).strip() if len(parents) > 1 else ""
        canonical_name = normalize_report_name(func_name)
        items.append(
            {
                **item,
                "canonicalName": canonical_name,
                "rootName": root_name,
                "groupName": group_name,
                "menuPath": list(parents) + [func_name],
            }
        )
    return items


def list_report_menu_items(menu_list: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in list_menu_items(menu_list)
        if item.get("rootName") == REPORT_ROOT_NAME
    ]


def build_menu_lookup(menu_list: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for item in list_menu_items(menu_list):
        lookup[item["FuncName"]] = item
        lookup[item["canonicalName"]] = item
        lookup[f'{item["rootName"]}::{item["FuncName"]}'] = item
        lookup[f'{item["rootName"]}::{item["canonicalName"]}'] = item
    for alias, canonical in REPORT_ALIAS_MAP.items():
        if canonical in lookup and alias not in lookup:
            lookup[alias] = lookup[canonical]
        report_key = f"{REPORT_ROOT_NAME}::{canonical}"
        alias_key = f"{REPORT_ROOT_NAME}::{alias}"
        if report_key in lookup and alias_key not in lookup:
            lookup[alias_key] = lookup[report_key]
    for research_title, override in RESEARCH_PAGE_OVERRIDES.items():
        target_title = override.get("menu_target_title", research_title)
        root_name = override.get("menu_root_name", REPORT_ROOT_NAME)
        target_key = f"{root_name}::{target_title}"
        if target_key in lookup:
            lookup[research_title] = lookup[target_key]
            lookup[f"{root_name}::{research_title}"] = lookup[target_key]
    return lookup


def flatten_payload_paths(payload: Any, prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(flatten_payload_paths(value, next_prefix))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            next_prefix = f"{prefix}[{index}]"
            flattened.update(flatten_payload_paths(value, next_prefix))
    else:
        flattened[prefix] = payload
    return flattened


def diff_payload_paths(before: Any, after: Any) -> dict[str, Any]:
    left = flatten_payload_paths(before)
    right = flatten_payload_paths(after)
    changes: list[dict[str, Any]] = []
    for path in sorted(set(left) | set(right)):
        left_value = left.get(path)
        right_value = right.get(path)
        if left_value != right_value:
            changes.append(
                {
                    "path": path,
                    "before": left_value,
                    "after": right_value,
                }
            )
    return {
        "changed_paths": changes,
        "changed_count": len(changes),
    }


def set_nested_payload_value(payload: Any, path: str, value: Any) -> Any:
    copied = json.loads(json.dumps(payload, ensure_ascii=False))
    cursor = copied
    parts = path.split(".")
    for part in parts[:-1]:
        if not isinstance(cursor, Mapping):
            raise ValueError(f"路径 `{path}` 无法写入，`{part}` 不是对象")
        next_value = cursor.get(part)
        if not isinstance(next_value, Mapping):
            next_value = {}
            cursor[part] = next_value
        cursor = next_value
    if not isinstance(cursor, Mapping):
        raise ValueError(f"路径 `{path}` 无法写入，末级父对象不存在")
    cursor[parts[-1]] = value
    return copied


def get_probe_target_titles(target_name: str) -> tuple[str, ...]:
    return SECOND_ROUND_PROBE_TARGETS.get(target_name, ())


def _first_csv_token(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    token = next((item.strip() for item in value.split(",") if item.strip()), "")
    return token or None


def build_single_variable_probe_cases(entry: ResearchPageRegistryEntry) -> list[SingleVariableProbeCase]:
    sample_url = str(entry.sample_url or "")
    sample_payload = entry.sample_payload if isinstance(entry.sample_payload, Mapping) else None
    if entry.title == "销售清单" and sample_payload:
        detail_payload = json.loads(json.dumps(sample_payload, ensure_ascii=False))
        detail_begin = str(detail_payload.get("parameter", {}).get("BeginDate") or "")
        detail_end = str(detail_payload.get("parameter", {}).get("EndDate") or "")
        return [
            SingleVariableProbeCase(
                key="probe_sales_document_route",
                label="单变量探测：销售清单按单据路线",
                url=SALES_DOCUMENT_ROUTE_URL,
                payload=SALES_DOCUMENT_ROUTE_PAYLOAD,
                parameter_path="grain_route",
                parameter_value="document_header_route",
                category="grain_route",
                notes="_1 / SelSaleReport",
            ),
            SingleVariableProbeCase(
                key="probe_sales_detail_route",
                label="单变量探测：销售清单按明细路线",
                url=sample_url,
                payload=detail_payload,
                parameter_path="grain_route",
                parameter_value="line_detail_route",
                category="grain_route",
                notes="_2 / GetDIYReportData",
            ),
            SingleVariableProbeCase(
                key="probe_sales_tiem_0",
                label="单变量探测：销售清单 Tiem=0",
                url=sample_url,
                payload=set_nested_payload_value(detail_payload, "parameter.Tiem", "0"),
                parameter_path="parameter.Tiem",
                parameter_value="0",
                category="enum",
                reference_payload=detail_payload,
            ),
            SingleVariableProbeCase(
                key="probe_sales_tiem_1",
                label="单变量探测：销售清单 Tiem=1",
                url=sample_url,
                payload=set_nested_payload_value(detail_payload, "parameter.Tiem", "1"),
                parameter_path="parameter.Tiem",
                parameter_value="1",
                category="enum",
                reference_payload=detail_payload,
            ),
            SingleVariableProbeCase(
                key="probe_sales_tiem_2",
                label="单变量探测：销售清单 Tiem=2",
                url=sample_url,
                payload=set_nested_payload_value(detail_payload, "parameter.Tiem", "2"),
                parameter_path="parameter.Tiem",
                parameter_value="2",
                category="enum",
                reference_payload=detail_payload,
            ),
            SingleVariableProbeCase(
                key="probe_sales_begin_date",
                label="单变量探测：销售清单 BeginDate=EndDate",
                url=sample_url,
                payload=set_nested_payload_value(detail_payload, "parameter.BeginDate", detail_end),
                parameter_path="parameter.BeginDate",
                parameter_value=detail_end,
                category="date",
                reference_payload=detail_payload,
            ),
            SingleVariableProbeCase(
                key="probe_sales_end_date",
                label="单变量探测：销售清单 EndDate=BeginDate",
                url=sample_url,
                payload=set_nested_payload_value(detail_payload, "parameter.EndDate", detail_begin),
                parameter_path="parameter.EndDate",
                parameter_value=detail_begin,
                category="date",
                reference_payload=detail_payload,
            ),
            SingleVariableProbeCase(
                key="probe_sales_depart_blank",
                label="单变量探测：销售清单 Depart 置空",
                url=sample_url,
                payload=set_nested_payload_value(detail_payload, "parameter.Depart", ""),
                parameter_path="parameter.Depart",
                parameter_value="",
                category="scope",
                reference_payload=detail_payload,
            ),
        ]
    if entry.title == "零售明细统计" and sample_payload:
        paged_baseline = set_nested_payload_value(sample_payload, "pagesize", 20)
        return [
            SingleVariableProbeCase(
                key="probe_retail_pagesize_20",
                label="单变量探测：零售明细统计 pagesize=20",
                url=sample_url,
                payload=paged_baseline,
                parameter_path="pagesize",
                parameter_value=20,
                category="pagination",
                reference_payload=sample_payload,
            ),
            SingleVariableProbeCase(
                key="probe_retail_page_1",
                label="单变量探测：零售明细统计 page=1",
                url=sample_url,
                payload=set_nested_payload_value(paged_baseline, "page", 1),
                parameter_path="page",
                parameter_value=1,
                category="pagination",
                reference_payload=paged_baseline,
            ),
            SingleVariableProbeCase(
                key="probe_retail_same_day",
                label="单变量探测：零售明细统计 edate=bdate",
                url=sample_url,
                payload=set_nested_payload_value(sample_payload, "edate", sample_payload.get("bdate")),
                parameter_path="edate",
                parameter_value=sample_payload.get("bdate"),
                category="date",
                reference_payload=sample_payload,
            ),
        ]
    if entry.title == "库存明细统计" and sample_payload:
        return [
            SingleVariableProbeCase(
                key=f"probe_stockflag_{value}",
                label=f"单变量探测：库存明细统计 stockflag={value}",
                url=sample_url,
                payload=set_nested_payload_value(sample_payload, "stockflag", value),
                parameter_path="stockflag",
                parameter_value=value,
                category="enum",
                reference_payload=sample_payload,
            )
            for value in ("0", "1", "2")
        ]
    if entry.title == "出入库单据" and sample_payload:
        first_type = _first_csv_token(sample_payload.get("type"))
        first_doctype = _first_csv_token(sample_payload.get("doctype"))
        cases = [
            SingleVariableProbeCase(
                key=f"probe_outin_datetype_{value}",
                label=f"单变量探测：出入库单据 datetype={value}",
                url=sample_url,
                payload=set_nested_payload_value(sample_payload, "datetype", value),
                parameter_path="datetype",
                parameter_value=value,
                category="enum",
                reference_payload=sample_payload,
            )
            for value in ("1", "2")
        ]
        if first_type is not None:
            cases.append(
                SingleVariableProbeCase(
                    key="probe_outin_type_single",
                    label=f"单变量探测：出入库单据 type={first_type}",
                    url=sample_url,
                    payload=set_nested_payload_value(sample_payload, "type", first_type),
                    parameter_path="type",
                    parameter_value=first_type,
                    category="scope",
                    reference_payload=sample_payload,
                )
            )
        if first_doctype is not None:
            cases.append(
                SingleVariableProbeCase(
                    key="probe_outin_doctype_single",
                    label=f"单变量探测：出入库单据 doctype={first_doctype}",
                    url=sample_url,
                    payload=set_nested_payload_value(sample_payload, "doctype", first_doctype),
                    parameter_path="doctype",
                    parameter_value=first_doctype,
                    category="scope",
                    reference_payload=sample_payload,
                )
            )
        return cases
    if entry.title in {
        "库存总和分析-按年份季节",
        "库存总和分析-按中分类",
        "库存总和分析-按波段",
        "库存综合分析-按年份季节",
        "库存综合分析-按中分类",
        "库存综合分析-按波段分析",
    } and sample_payload:
        return [
            SingleVariableProbeCase(
                key=f"probe_stock_analysis_rtype_{value}",
                label=f"单变量探测：库存综合分析 rtype={value}",
                url=sample_url,
                payload=set_nested_payload_value(sample_payload, "rtype", value),
                parameter_path="rtype",
                parameter_value=value,
                category="enum",
                reference_payload=sample_payload,
            )
            for value in (1, 2, 3)
        ]
    return []


def _classify_payload_hints(payload: Any) -> dict[str, list[str]]:
    flattened = flatten_payload_paths(payload)
    result = {
        "date_fields": [],
        "org_fields": [],
        "search_fields": [],
        "enum_fields": [],
        "pagination_fields": [],
        "diy_context_fields": [],
    }
    for path in flattened:
        tail = re.sub(r"\[\d+\]", "", path.split(".")[-1]).lower()
        if tail in DATE_FIELD_HINTS:
            result["date_fields"].append(path)
        if tail in ORG_FIELD_HINTS:
            result["org_fields"].append(path)
        if tail in SEARCH_FIELD_HINTS:
            result["search_fields"].append(path)
        if tail in ENUM_FIELD_HINTS:
            result["enum_fields"].append(path)
        if tail in PAGINATION_FIELD_HINTS:
            result["pagination_fields"].append(path)
        if tail in DIY_CONTEXT_HINTS:
            result["diy_context_fields"].append(path)
    return {key: sorted(values) for key, values in result.items() if values}


def extract_endpoint_name(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if not path:
        return ""
    return path.split("/")[-1]


def is_interesting_endpoint(url: str) -> bool:
    return any(keyword in url for keyword in INTERESTING_ENDPOINTS)


def is_likely_data_endpoint(url: str) -> bool:
    endpoint = extract_endpoint_name(url)
    if endpoint in NON_DATA_ENDPOINTS:
        return False
    if any(keyword in url for keyword in ("GetDIYReportData", "Sel", "Report", "Analysis", "Slip")):
        return True
    return False


def summarize_network_entry(
    *,
    request: Mapping[str, Any],
    response: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    post_data = request.get("post_data")
    payload_hints = _classify_payload_hints(post_data) if post_data is not None else {}
    response_summary = response.get("response_summary") if response else None
    return {
        "endpoint": extract_endpoint_name(str(request.get("url") or "")),
        "url": request.get("url"),
        "method": request.get("method"),
        "payload_hints": payload_hints,
        "response_summary": response_summary,
    }


def _choose_primary_probe_fingerprint(step: Mapping[str, Any]) -> dict[str, Any] | None:
    fingerprints = [
        item
        for item in step.get("response_fingerprints") or []
        if item.get("is_data_endpoint")
    ]
    if not fingerprints:
        fingerprints = list(step.get("response_fingerprints") or [])
    if not fingerprints:
        return None
    ranked = sorted(
        fingerprints,
        key=lambda item: (
            int(item.get("row_count") or 0),
            0 if item.get("row_set_signature") else -1,
            0 if item.get("columns_signature") else -1,
        ),
        reverse=True,
    )
    return ranked[0]


def _classify_probe_variants(variants: Sequence[Mapping[str, Any]]) -> str:
    usable = [
        item
        for item in variants
        if item.get("row_set_signature") or item.get("columns_signature")
    ]
    if len(usable) <= 1:
        return "insufficient_evidence"
    row_set_count = len({item.get("row_set_signature") for item in usable})
    columns_count = len({item.get("columns_signature") for item in usable})
    if row_set_count == 1 and columns_count == 1:
        return "same_dataset"
    if row_set_count > 1 and columns_count == 1:
        return "data_subset_or_scope_switch"
    if row_set_count == 1 and columns_count > 1:
        return "view_switch"
    return "mixed"


def _recommended_strategy_for_semantics(semantics: str) -> str:
    if semantics == "same_dataset":
        return "single_request"
    if semantics == "data_subset_or_scope_switch":
        return "枚举 sweep"
    if semantics == "view_switch":
        return "结果快照"
    if semantics == "mixed":
        return "split_routes"
    return "needs_followup"


def _collect_probe_summary(actions: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    probe_steps = [action for action in actions if action.get("probe")]
    results: list[dict[str, Any]] = []
    grouped_variants: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for step in probe_steps:
        probe = step.get("probe") or {}
        primary = _choose_primary_probe_fingerprint(step) or {}
        result = {
            "action_key": step.get("key"),
            "label": step.get("label"),
            "parameter_path": probe.get("parameter_path"),
            "parameter_value": probe.get("parameter_value"),
            "category": probe.get("category"),
            "notes": probe.get("notes"),
            "request_diffs": step.get("request_diffs") or [],
            "response_fingerprints": step.get("response_fingerprints") or [],
            "primary_fingerprint": primary,
        }
        results.append(result)
        if probe.get("parameter_path"):
            grouped_variants[str(probe["parameter_path"])].append(
                {
                    "value": probe.get("parameter_value"),
                    "category": probe.get("category"),
                    "notes": probe.get("notes"),
                    "endpoint": primary.get("endpoint"),
                    "row_count": primary.get("row_count"),
                    "columns_signature": primary.get("columns_signature"),
                    "row_set_signature": primary.get("row_set_signature"),
                }
            )

    parameter_semantics: dict[str, Any] = {}
    for path, variants in grouped_variants.items():
        semantics = _classify_probe_variants(variants)
        parameter_semantics[path] = {
            "parameter_path": path,
            "semantics": semantics,
            "recommended_http_strategy": _recommended_strategy_for_semantics(semantics),
            "variants": variants,
        }
    return results, parameter_semantics


def _collect_grid_ids(requests: Sequence[Mapping[str, Any]]) -> set[str]:
    grid_ids: set[str] = set()
    for request in requests:
        post_data = request.get("post_data")
        flattened = flatten_payload_paths(post_data) if post_data is not None else {}
        for path, value in flattened.items():
            if path.endswith("gridid") and value:
                grid_ids.add(str(value))
    return grid_ids


def _collect_payload_hint_union(requests: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    bucket: dict[str, set[str]] = defaultdict(set)
    for request in requests:
        for key, values in _classify_payload_hints(request.get("post_data")).items():
            bucket[key].update(values)
    return {key: sorted(values) for key, values in bucket.items()}


def _group_endpoint_summaries(
    requests: Sequence[Mapping[str, Any]],
    responses: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    response_by_request_id = {item.get("request_id"): item for item in responses if item.get("request_id") is not None}
    buckets: dict[str, dict[str, Any]] = {}
    for request in requests:
        endpoint = extract_endpoint_name(str(request.get("url") or ""))
        if endpoint not in buckets:
            buckets[endpoint] = {
                "endpoint": endpoint,
                "request_count": 0,
                "response_count": 0,
                "max_row_count": 0,
                "response_shapes": set(),
                "grid_ids": set(),
                "menu_ids": set(),
                "is_data_endpoint": is_likely_data_endpoint(str(request.get("url") or "")),
            }
        bucket = buckets[endpoint]
        bucket["request_count"] += 1
        flattened = flatten_payload_paths(request.get("post_data"))
        for path, value in flattened.items():
            if path.endswith("gridid") and value:
                bucket["grid_ids"].add(str(value))
            if path.endswith("menuid") and value:
                bucket["menu_ids"].add(str(value))
        response = response_by_request_id.get(request.get("id"))
        if response:
            bucket["response_count"] += 1
            summary = response.get("response_summary") or {}
            bucket["max_row_count"] = max(bucket["max_row_count"], int(summary.get("row_count") or 0))
            if summary.get("response_shape"):
                bucket["response_shapes"].add(summary["response_shape"])

    result = []
    for bucket in buckets.values():
        result.append(
            {
                **bucket,
                "grid_ids": sorted(bucket["grid_ids"]),
                "menu_ids": sorted(bucket["menu_ids"]),
                "response_shapes": sorted(bucket["response_shapes"]),
            }
        )
    result.sort(key=lambda item: (-int(item["is_data_endpoint"]), -item["max_row_count"], item["endpoint"]))
    return result


def build_page_manifest_summary(manifest: Mapping[str, Any]) -> dict[str, Any]:
    requests = manifest.get("network", {}).get("requests") or []
    responses = manifest.get("network", {}).get("responses") or []
    endpoint_summaries = _group_endpoint_summaries(requests, responses)
    payload_hints = _collect_payload_hint_union(requests)
    grid_ids = _collect_grid_ids(requests)
    endpoints = {item["endpoint"] for item in endpoint_summaries}

    grain_route = "single_route"
    candidate_join_keys: list[str] = []
    probe_results, parameter_semantics = _collect_probe_summary(manifest.get("actions") or [])
    baseline_signatures = []
    for step in manifest.get("actions") or []:
        if step.get("key") not in {"query", "variant_1_query", "variant_2_query"}:
            continue
        signatures = [
            fingerprint
            for fingerprint in step.get("response_fingerprints") or []
            if fingerprint.get("is_data_endpoint")
        ]
        if signatures:
            baseline_signatures.extend(signatures)

    if (
        {"GetDIYReportData", "SelSaleReport"} <= endpoints
        or (
            {"GetViewGridList", "GetDIYReportData", "SelSaleReport"} & endpoints
            and any(grid_id.endswith("_1") for grid_id in grid_ids)
            and any(grid_id.endswith("_2") for grid_id in grid_ids)
        )
    ):
        grain_route = "multi_grain_route"
        candidate_join_keys = ["sale_no", "sale_date", "operator", "vip_card_no"]
    elif payload_hints.get("enum_fields"):
        grain_route = "enum_or_scope_route"

    source_candidates = [
        item["endpoint"]
        for item in endpoint_summaries
        if item["is_data_endpoint"] and item["max_row_count"] > 0
    ]
    result_snapshot_candidates = [
        item["endpoint"]
        for item in endpoint_summaries
        if not item["is_data_endpoint"]
    ]

    if grain_route == "multi_grain_route":
        recommended_capture_strategy = "split_head_and_line_routes"
    elif payload_hints.get("pagination_fields") and payload_hints.get("enum_fields"):
        recommended_capture_strategy = "http_followup_with_pagination_and_enum"
    elif payload_hints.get("pagination_fields"):
        recommended_capture_strategy = "http_followup_with_pagination"
    elif payload_hints.get("enum_fields"):
        recommended_capture_strategy = "http_followup_with_enum_probe"
    else:
        recommended_capture_strategy = "baseline_single_request"

    return {
        "title": manifest.get("page", {}).get("title"),
        "menu_target_title": manifest.get("page", {}).get("menu_target_title"),
        "menu_root_name": manifest.get("page", {}).get("menu_root_name"),
        "group_name": manifest.get("page", {}).get("group_name"),
        "menu_path": manifest.get("page", {}).get("menu_path") or [],
        "target_menu_path": manifest.get("page", {}).get("target_menu_path") or [],
        "variant_label": manifest.get("page", {}).get("variant_label"),
        "variant_of": manifest.get("page", {}).get("variant_of"),
        "status": manifest.get("status"),
        "endpoint_summaries": endpoint_summaries,
        "payload_hints": payload_hints,
        "grid_ids": sorted(grid_ids),
        "grain_route": grain_route,
        "source_candidates": source_candidates,
        "result_snapshot_candidates": result_snapshot_candidates,
        "recommended_capture_strategy": recommended_capture_strategy,
        "candidate_join_keys": candidate_join_keys,
        "baseline_request_signature": baseline_signatures,
        "single_variable_probe_results": probe_results,
        "parameter_semantics": parameter_semantics,
        "visible_control_count": len(manifest.get("visible_controls") or []),
    }


def summarize_page_manifests(manifests: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    success_pages = [item for item in manifests if item.get("status") == "ok"]
    failed_pages = [item for item in manifests if item.get("status") != "ok"]
    return {
        "page_count": len(manifests),
        "success_count": len(success_pages),
        "failed_count": len(failed_pages),
        "failed_pages": [
            {
                "title": item.get("page", {}).get("title"),
                "error": item.get("error"),
            }
            for item in failed_pages
        ],
        "pages": [
            {**page_summary, "summary": page_summary}
            for item in manifests
            for page_summary in [build_page_manifest_summary(item)]
        ],
    }


def load_page_research_manifests(run_dir: Path) -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    for manifest_path in sorted(run_dir.glob("*/manifest.json")):
        manifests.append(json.loads(manifest_path.read_text("utf-8")))
    return manifests
