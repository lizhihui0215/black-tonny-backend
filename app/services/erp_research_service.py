from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any


DATE_FIELD_HINTS = {
    "bdate",
    "edate",
    "begindate",
    "enddate",
    "salebdate",
    "saleedate",
    "birthbdate",
    "birthedate",
    "lastdate",
    "ybegindate",
    "yenddate",
    "mbegindate",
    "menddate",
    "date1",
}

ORG_FIELD_HINTS = {
    "depart",
    "depts",
    "warecause",
    "wareclause",
    "operater",
    "spenum",
    "volumenumber",
}

SEARCH_FIELD_HINTS = {
    "search",
    "searchtype",
    "condition",
    "searchval",
    "name",
    "tag",
}

ENUM_FIELD_HINTS = {
    "rtype",
    "type",
    "datetype",
    "stockflag",
    "doctype",
    "tiem",
    "sort",
}

PAGINATION_FIELD_HINTS = {
    "page",
    "pagesize",
    "pageindex",
    "pagesize",
}

DIY_CONTEXT_HINTS = {
    "menuid",
    "gridid",
}

COST_FIELD_PATTERN = re.compile(r"(成本|cost)", re.IGNORECASE)
PRICE_FIELD_PATTERN = re.compile(r"(吊牌|零售|售价|牌价|RetailPrice|TagPrice|Price)", re.IGNORECASE)


@dataclass(frozen=True)
class EnumProbeSpec:
    path: str
    candidates: tuple[Any, ...]


@dataclass(frozen=True)
class PaginationProbeSpec:
    page_path: str
    page_size_path: str
    start_page: int = 0
    paged_size: int = 20
    include_zero_size_probe: bool = False


@dataclass(frozen=True)
class ExplorationStrategy:
    title: str
    pagination: PaginationProbeSpec | None = None
    enum_probes: tuple[EnumProbeSpec, ...] = ()
    context_fields: tuple[str, ...] = ()
    combine_enum_with_pagination: bool = False
    result_snapshot: bool = False


EXPLORATION_TARGETS: dict[str, tuple[str, ...]] = {
    "sales_inventory": (
        "销售清单",
        "零售明细统计",
        "库存明细统计",
        "出入库单据",
    )
}

EXPLORATION_STRATEGIES: dict[str, ExplorationStrategy] = {
    "零售明细统计": ExplorationStrategy(
        title="零售明细统计",
        pagination=PaginationProbeSpec(
            page_path="page",
            page_size_path="pagesize",
            start_page=0,
            paged_size=20,
            include_zero_size_probe=True,
        ),
    ),
    "销售清单": ExplorationStrategy(
        title="销售清单",
        enum_probes=(
            EnumProbeSpec(
                path="parameter.Tiem",
                candidates=("0", "1", "2"),
            ),
        ),
        context_fields=("parameter.Depart",),
    ),
    "库存明细统计": ExplorationStrategy(
        title="库存明细统计",
        pagination=PaginationProbeSpec(
            page_path="page",
            page_size_path="pagesize",
            start_page=0,
            paged_size=20,
        ),
        enum_probes=(
            EnumProbeSpec(
                path="stockflag",
                candidates=("0", "1", "2"),
            ),
        ),
        combine_enum_with_pagination=True,
    ),
    "出入库单据": ExplorationStrategy(
        title="出入库单据",
        pagination=PaginationProbeSpec(
            page_path="page",
            page_size_path="pagesize",
            start_page=0,
            paged_size=20,
            include_zero_size_probe=True,
        ),
        enum_probes=(
            EnumProbeSpec(
                path="datetype",
                candidates=("1", "2"),
            ),
        ),
        context_fields=("type", "doctype"),
        combine_enum_with_pagination=True,
    ),
}


def slugify(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", value, flags=re.UNICODE)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "report"


def parse_data_raw(block: str) -> dict[str, Any] | list[Any] | str:
    match = re.search(r"--data-raw\s+(\$?)(['\"])(.*)\2", block, re.DOTALL)
    if not match:
        return {}
    raw = match.group(3).strip()
    if match.group(1) == "$":
        raw = bytes(raw, "utf-8").decode("unicode_escape")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def parse_report_specs(doc_path: Path) -> list[dict[str, Any]]:
    text = doc_path.read_text("utf-8")
    pattern = re.compile(r"^###\s+(.+?)\n+```bash\n(.*?)```", re.MULTILINE | re.DOTALL)
    specs: list[dict[str, Any]] = []
    for title, block in pattern.findall(text):
        if title in {"CompanyUserPassWord", "Login"}:
            continue
        url_match = re.search(r"curl\s+'([^']+)'", block)
        if not url_match:
            continue
        specs.append(
            {
                "title": title.strip(),
                "url": url_match.group(1).strip(),
                "payload": parse_data_raw(block),
                "filename": f"{slugify(title)}.json",
            }
        )
    return specs


def flatten_payload(payload: Any, prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(flatten_payload(value, next_prefix))
        return flattened
    if isinstance(payload, list):
        flattened[prefix] = payload
        return flattened
    flattened[prefix] = payload
    return flattened


def _leaf_name(path: str) -> str:
    return path.split(".")[-1].lower()


def classify_filter_fields(payload: Any) -> dict[str, list[dict[str, Any]]]:
    flat = flatten_payload(payload)
    categories = {
        "date_fields": [],
        "organization_fields": [],
        "search_fields": [],
        "enum_fields": [],
        "pagination_fields": [],
        "diy_context_fields": [],
        "other_fields": [],
    }
    for path, value in flat.items():
        if not path:
            continue
        leaf = _leaf_name(path)
        item = {"path": path, "value": value}
        if leaf in DATE_FIELD_HINTS:
            categories["date_fields"].append(item)
        elif leaf in ORG_FIELD_HINTS:
            categories["organization_fields"].append(item)
        elif leaf in SEARCH_FIELD_HINTS:
            categories["search_fields"].append(item)
        elif leaf in ENUM_FIELD_HINTS or (isinstance(value, str) and "," in value):
            categories["enum_fields"].append(item)
        elif leaf in PAGINATION_FIELD_HINTS:
            categories["pagination_fields"].append(item)
        elif leaf in DIY_CONTEXT_HINTS or path.startswith("parameter."):
            categories["diy_context_fields"].append(item)
        else:
            categories["other_fields"].append(item)
    return categories


def infer_auth_mode(url: str) -> str:
    return "Authorization" if "/JyApi/" in url else "token"


def infer_domain(title: str) -> str:
    if any(key in title for key in ("销售", "零售", "商品")):
        return "sales"
    if any(key in title for key in ("库存", "进销存", "出入库")):
        return "inventory"
    if "会员" in title:
        return "member"
    if "储值" in title:
        return "stored_value"
    if any(key in title for key in ("流水", "月报", "单据")):
        return "payment_and_docs"
    return "unknown"


def infer_risk_labels(filter_fields: dict[str, list[dict[str, Any]]], title: str) -> list[str]:
    risks: list[str] = []
    if filter_fields["pagination_fields"]:
        risks.append("需要翻页")
    if filter_fields["enum_fields"]:
        risks.append("需要扫枚举")
    if filter_fields["diy_context_fields"]:
        risks.append("DIY 报表隐藏条件")
    if any(key in title for key in ("分析", "排行", "月报")):
        risks.append("结果视图重叠风险")
    return risks


def infer_capture_strategy(risk_labels: Sequence[str], title: str) -> str:
    if "结果视图重叠风险" in risk_labels and any(key in title for key in ("分析", "排行", "月报")):
        return "结果快照"
    if "需要扫枚举" in risk_labels:
        return "枚举 sweep"
    if "需要翻页" in risk_labels:
        return "自动翻页"
    return "单请求"


def infer_source_kind(title: str) -> str:
    if any(key in title for key in ("清单", "明细", "单据", "中心")):
        return "源接口候选"
    if any(key in title for key in ("分析", "排行", "月报", "统计")):
        return "结果快照候选"
    return "待判断"


def _extract_table_data(payload: Any) -> tuple[list[str], list[Any], str]:
    if isinstance(payload, Mapping) and isinstance(payload.get("retdata"), Mapping):
        retdata = payload["retdata"]
        if isinstance(retdata.get("ColumnsList"), list) and isinstance(retdata.get("Data"), list):
            return list(retdata["ColumnsList"]), list(retdata["Data"]), "retdata.ColumnsList+Data"

    if isinstance(payload, Mapping) and isinstance(payload.get("retdata"), list):
        for item in payload["retdata"]:
            if isinstance(item, Mapping) and isinstance(item.get("ColumnsList"), list) and isinstance(item.get("Data"), list):
                return list(item["ColumnsList"]), list(item["Data"]), "retdata[].ColumnsList+Data"
            if isinstance(item, Mapping) and isinstance(item.get("Title"), list) and isinstance(item.get("Data"), list):
                rows = list(item["Data"])
                columns = list(rows[0].keys()) if rows and isinstance(rows[0], Mapping) else []
                return columns, rows, "retdata[].Title+Data"

    if isinstance(payload, Mapping) and isinstance(payload.get("Data"), Mapping):
        data = payload["Data"]
        if isinstance(data.get("Columns"), list) and isinstance(data.get("List"), list):
            return list(data["Columns"]), list(data["List"]), "Data.Columns+List"

    if isinstance(payload, Mapping) and isinstance(payload.get("PageData"), Mapping):
        page_data = payload["PageData"]
        if isinstance(page_data.get("Items"), list):
            rows = list(page_data["Items"])
            columns = list(rows[0].keys()) if rows and isinstance(rows[0], Mapping) else []
            return columns, rows, "PageData.Items"

    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if isinstance(value, list) and value:
                if isinstance(value[0], Mapping):
                    return list(value[0].keys()), list(value), f"{key}[]"
                if isinstance(value[0], list):
                    return [], list(value), f"{key}[[]]"

    return [], [], "unknown"


def _field_stats(columns: list[str], rows: list[Any]) -> dict[str, Any]:
    cost_fields: list[dict[str, Any]] = []
    price_fields: list[dict[str, Any]] = []

    if columns and rows and isinstance(rows[0], list):
        for index, column in enumerate(columns):
            values = [row[index] if index < len(row) else None for row in rows]
            stat = {
                "field": column,
                "non_null_count": sum(1 for value in values if value not in (None, "", "null")),
            }
            if COST_FIELD_PATTERN.search(column):
                cost_fields.append(stat)
            if PRICE_FIELD_PATTERN.search(column):
                price_fields.append(stat)
        return {
            "cost_fields": cost_fields,
            "price_fields": price_fields,
        }

    if rows and isinstance(rows[0], Mapping):
        keys = columns or list(rows[0].keys())
        for key in keys:
            values = [row.get(key) for row in rows if isinstance(row, Mapping)]
            stat = {
                "field": key,
                "non_null_count": sum(1 for value in values if value not in (None, "", "null")),
            }
            if COST_FIELD_PATTERN.search(key):
                cost_fields.append(stat)
            if PRICE_FIELD_PATTERN.search(key):
                price_fields.append(stat)
        return {
            "cost_fields": cost_fields,
            "price_fields": price_fields,
        }

    return {
        "cost_fields": [],
        "price_fields": [],
    }


def _build_row_signature(rows: list[Any], limit: int = 5) -> str:
    preview = rows[:limit]
    raw = json.dumps(preview, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    digest = hashlib.sha1(f"{len(rows)}|{raw}".encode("utf-8")).hexdigest()
    return digest[:16]


def analyze_response_payload(payload: Any, *, sample_path: str | None = None) -> dict[str, Any]:
    columns, rows, shape = _extract_table_data(payload)
    field_stats = _field_stats(columns, rows)
    result = {
        "response_shape": shape,
        "row_count": len(rows),
        "column_count": len(columns),
        "columns_preview": columns[:20],
        "row_signature": _build_row_signature(rows),
        "cost_fields": field_stats["cost_fields"],
        "price_fields": field_stats["price_fields"],
    }
    if sample_path is not None:
        result["sample_path"] = sample_path
    return result


def analyze_response_sample(sample_path: Path) -> dict[str, Any]:
    payload = json.loads(sample_path.read_text("utf-8"))
    return analyze_response_payload(payload, sample_path=str(sample_path))


def find_latest_sample(raw_root: Path, title: str) -> Path | None:
    target_name = f"{title}.json"
    candidates = sorted(raw_root.glob(f"*/{target_name}"))
    return candidates[-1] if candidates else None


def build_report_matrix(report_doc_path: Path, raw_root: Path) -> list[dict[str, Any]]:
    matrix: list[dict[str, Any]] = []
    for spec in parse_report_specs(report_doc_path):
        filter_fields = classify_filter_fields(spec["payload"])
        risk_labels = infer_risk_labels(filter_fields, spec["title"])
        sample_path = find_latest_sample(raw_root, spec["title"])
        sample_analysis = analyze_response_sample(sample_path) if sample_path else None
        matrix.append(
            {
                "title": spec["title"],
                "domain": infer_domain(spec["title"]),
                "url": spec["url"],
                "auth_mode": infer_auth_mode(spec["url"]),
                "source_kind": infer_source_kind(spec["title"]),
                "capture_strategy": infer_capture_strategy(risk_labels, spec["title"]),
                "risk_labels": risk_labels,
                "filter_fields": filter_fields,
                "sample_analysis": sample_analysis,
            }
        )
    return matrix


def get_exploration_target_titles(target: str) -> tuple[str, ...]:
    if target not in EXPLORATION_TARGETS:
        raise KeyError(target)
    return EXPLORATION_TARGETS[target]


def get_exploration_strategy(title: str) -> ExplorationStrategy | None:
    return EXPLORATION_STRATEGIES.get(title)


def should_persist_capture(mode: str, *, skip_db: bool, persist_detection: bool) -> bool:
    if skip_db:
        return False
    if mode == "explore":
        return persist_detection
    return True


def _get_payload_value(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _set_payload_value(payload: Any, path: str, value: Any) -> None:
    current = payload
    parts = path.split(".")
    for part in parts[:-1]:
        if not isinstance(current, dict):
            raise TypeError(f"路径 {path} 无法写入")
        current = current.setdefault(part, {})
    if not isinstance(current, dict):
        raise TypeError(f"路径 {path} 无法写入")
    current[parts[-1]] = value


def _dedupe_candidates(sample_value: Any, candidates: Sequence[Any], limit: int) -> list[Any]:
    result: list[Any] = []
    for candidate in (sample_value, *candidates):
        if candidate in result or candidate is None:
            continue
        result.append(candidate)
        if len(result) >= limit:
            break
    return result


def _json_signature(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_exploration_cases(
    report_spec: Mapping[str, Any],
    strategy: ExplorationStrategy,
    *,
    max_pages: int,
    enum_limit: int,
) -> list[dict[str, Any]]:
    base_payload = copy.deepcopy(report_spec["payload"])
    if not isinstance(base_payload, dict):
        raise TypeError("当前探索模式只支持 JSON object payload")

    cases: list[dict[str, Any]] = []
    seen_signatures: set[tuple[str, str]] = set()

    def add_case(kind: str, payload: dict[str, Any], label_parts: list[str], probe_context: dict[str, Any]) -> None:
        signature = _json_signature(payload)
        dedupe_key = (kind, signature)
        if dedupe_key in seen_signatures:
            return
        seen_signatures.add(dedupe_key)
        case_id = slugify("__".join([strategy.title, kind, *label_parts]))
        cases.append(
            {
                "case_id": case_id,
                "kind": kind,
                "label": " | ".join(label_parts) if label_parts else "base",
                "payload": payload,
                "probe_context": probe_context,
            }
        )

    add_case("base", copy.deepcopy(base_payload), [], {"context_fields": list(strategy.context_fields)})

    enum_variants = [({"payload": copy.deepcopy(base_payload), "labels": [], "context": {}})]
    if strategy.enum_probes:
        enum_variants = []
        candidate_lists: list[tuple[EnumProbeSpec, list[Any]]] = []
        for enum_probe in strategy.enum_probes:
            sample_value = _get_payload_value(base_payload, enum_probe.path)
            candidates = _dedupe_candidates(sample_value, enum_probe.candidates, enum_limit)
            candidate_lists.append((enum_probe, candidates))

        for combination in product(*[candidates for _, candidates in candidate_lists]):
            payload = copy.deepcopy(base_payload)
            labels: list[str] = []
            context: dict[str, Any] = {}
            for (enum_probe, _), candidate in zip(candidate_lists, combination):
                _set_payload_value(payload, enum_probe.path, candidate)
                labels.append(f"{enum_probe.path}={candidate}")
                context[enum_probe.path] = candidate
            enum_variants.append({"payload": payload, "labels": labels, "context": context})

        if not strategy.combine_enum_with_pagination:
            for variant in enum_variants:
                add_case("enum", variant["payload"], variant["labels"], variant["context"])

    pagination = strategy.pagination
    if pagination:
        variants = enum_variants if strategy.combine_enum_with_pagination else [{"payload": copy.deepcopy(base_payload), "labels": [], "context": {}}]
        for variant in variants:
            if pagination.include_zero_size_probe:
                payload = copy.deepcopy(variant["payload"])
                _set_payload_value(payload, pagination.page_path, pagination.start_page)
                _set_payload_value(payload, pagination.page_size_path, 0)
                add_case(
                    "pagination",
                    payload,
                    [*variant["labels"], f"{pagination.page_path}={pagination.start_page}", f"{pagination.page_size_path}=0"],
                    {
                        **variant["context"],
                        pagination.page_path: pagination.start_page,
                        pagination.page_size_path: 0,
                    },
                )

            for offset in range(max_pages):
                page_value = pagination.start_page + offset
                payload = copy.deepcopy(variant["payload"])
                _set_payload_value(payload, pagination.page_path, page_value)
                _set_payload_value(payload, pagination.page_size_path, pagination.paged_size)
                add_case(
                    "pagination",
                    payload,
                    [
                        *variant["labels"],
                        f"{pagination.page_path}={page_value}",
                        f"{pagination.page_size_path}={pagination.paged_size}",
                    ],
                    {
                        **variant["context"],
                        pagination.page_path: page_value,
                        pagination.page_size_path: pagination.paged_size,
                    },
                )

    return cases


def summarize_exploration_results(
    strategy: ExplorationStrategy,
    probe_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    found_additional_pages = False
    enum_paths = tuple(enum_probe.path for enum_probe in strategy.enum_probes)
    risk_labels: list[str] = []

    def result_signature(result: Mapping[str, Any]) -> tuple[Any, ...]:
        analysis = result.get("analysis") or {}
        return (
            analysis.get("response_shape"),
            analysis.get("row_count"),
            analysis.get("column_count"),
            analysis.get("row_signature"),
        )

    def enum_scope_key(context: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
        return tuple((path, context.get(path)) for path in enum_paths if path in context)

    def is_usable_result(result: Mapping[str, Any]) -> bool:
        analysis = result.get("analysis") or {}
        return bool(analysis) and analysis.get("row_count", 0) > 0

    pagination_baselines: dict[tuple[tuple[str, Any], ...], tuple[Any, ...]] = {}
    if strategy.pagination:
        for result in probe_results:
            if not is_usable_result(result):
                continue
            context = result.get("probe_context") or {}
            if context.get(strategy.pagination.page_path) != strategy.pagination.start_page:
                continue
            page_size = context.get(strategy.pagination.page_size_path)
            if page_size not in (None, strategy.pagination.paged_size):
                continue
            pagination_baselines.setdefault(enum_scope_key(context), result_signature(result))

        for result in probe_results:
            if not is_usable_result(result):
                continue
            context = result.get("probe_context") or {}
            page_value = context.get(strategy.pagination.page_path)
            if not isinstance(page_value, int) or page_value <= strategy.pagination.start_page:
                continue
            baseline = pagination_baselines.get(enum_scope_key(context))
            if baseline is not None and result_signature(result) != baseline:
                found_additional_pages = True
                break

    enum_signatures_by_scope: dict[tuple[tuple[str, Any], ...], tuple[Any, ...]] = {}
    if enum_paths:
        for result in probe_results:
            if not is_usable_result(result):
                continue
            context = result.get("probe_context") or {}
            scope_key = enum_scope_key(context)
            if not scope_key:
                continue
            if strategy.pagination:
                page_value = context.get(strategy.pagination.page_path)
                page_size = context.get(strategy.pagination.page_size_path)
                if page_value != strategy.pagination.start_page:
                    continue
                if page_size not in (None, strategy.pagination.paged_size):
                    continue
            enum_signatures_by_scope.setdefault(scope_key, result_signature(result))

    found_distinct_enum_results = len(set(enum_signatures_by_scope.values())) > 1

    if strategy.result_snapshot:
        risk_labels.append("结果视图重叠风险")
        recommended = "结果快照"
    else:
        if found_distinct_enum_results:
            risk_labels.append("需要扫枚举")
        if found_additional_pages:
            risk_labels.append("需要翻页")

        if found_distinct_enum_results:
            recommended = "枚举 sweep"
        elif found_additional_pages:
            recommended = "自动翻页"
        else:
            recommended = "单请求"

    return {
        "found_additional_pages": found_additional_pages,
        "found_distinct_enum_results": found_distinct_enum_results,
        "risk_labels": risk_labels,
        "recommended_capture_strategy": recommended,
    }
