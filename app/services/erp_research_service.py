from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
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


def analyze_response_sample(sample_path: Path) -> dict[str, Any]:
    payload = json.loads(sample_path.read_text("utf-8"))
    columns, rows, shape = _extract_table_data(payload)
    field_stats = _field_stats(columns, rows)
    return {
        "sample_path": str(sample_path),
        "response_shape": shape,
        "row_count": len(rows),
        "column_count": len(columns),
        "columns_preview": columns[:20],
        "cost_fields": field_stats["cost_fields"],
        "price_fields": field_stats["price_fields"],
    }


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
