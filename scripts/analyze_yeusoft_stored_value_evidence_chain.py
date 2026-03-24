#!/usr/bin/env python3
from __future__ import annotations

import calendar
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.research.stored_value_evidence import build_stored_value_http_evidence_chain
from app.services.erp_research_service import extract_normalized_table_rows
from scripts.fetch_yeusoft_report_payloads import (
    LOCAL_TZ,
    README_PATH,
    REPORT_DOC_PATH,
    SAMPLES_DIR,
    build_report_auth_headers,
    curl_post_json,
    find_report_spec_by_title,
    maybe_override_url,
    now_local,
    read_login_auth,
    refresh_session_access_token,
    save_json,
)


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _build_quarterly_half_open_windows(begin_date: str, end_date: str) -> list[tuple[str, str]]:
    start = date(int(begin_date[:4]), int(begin_date[4:6]), int(begin_date[6:8]))
    end = date(int(end_date[:4]), int(end_date[4:6]), int(end_date[6:8]))
    windows: list[tuple[str, str]] = []
    current = start
    while current < end:
        next_date = _add_months(current, 3)
        if next_date > end:
            next_date = end
        windows.append((current.strftime("%Y%m%d"), next_date.strftime("%Y%m%d")))
        current = next_date
    return windows


def _extract_search_seed_values(payload: dict) -> dict[str, list[str]]:
    retdata = payload.get("retdata") or {}
    columns = retdata.get("ColumnsList") or []
    rows = retdata.get("Data") or []
    if not columns or not rows or not isinstance(rows[0], list):
        return {}

    samples = {
        "vip_card_id": [],
        "happen_no": [],
        "vip_name": [],
    }
    index_map = {str(column): idx for idx, column in enumerate(columns)}
    candidate_columns = {
        "vip_card_id": "VipCardId",
        "happen_no": "HappenNo",
        "vip_name": "VipName",
    }
    for row in rows:
        for key, column in candidate_columns.items():
            index = index_map.get(column)
            if index is None or index >= len(row):
                continue
            value = str(row[index] or "").strip()
            if value and value not in samples[key]:
                samples[key].append(value)
    return {key: values[:3] for key, values in samples.items() if values}


def _extract_first_row_context(payload: dict) -> dict[str, str]:
    normalized_rows = extract_normalized_table_rows(payload)
    if not normalized_rows:
        return {}
    first_row = normalized_rows[0]
    return {
        "vip_card_id": str(first_row.get("vip_card_no") or ""),
        "vip_name": str(first_row.get("vipname") or ""),
        "happen_no": str(first_row.get("happenno") or ""),
        "happen_date": str(first_row.get("happendate") or ""),
    }


def main() -> int:
    auth = read_login_auth(README_PATH)
    access_token, _ = refresh_session_access_token(auth)

    report_spec = find_report_spec_by_title(REPORT_DOC_PATH, "储值卡明细")
    if report_spec is None or not isinstance(report_spec.payload, dict):
        raise RuntimeError("未在 report_api_samples.md 中找到可用的 储值卡明细 payload")

    payload = dict(report_spec.payload)
    parameter = dict(payload.get("parameter") or {})
    url = maybe_override_url(report_spec, auth.raw_login_data.get("JyApiUrl") if auth.raw_login_data else auth.api_base_url)
    headers = build_report_auth_headers(url, access_token)

    _, baseline_response = curl_post_json(url, payload, headers)
    first_row_context = _extract_first_row_context(baseline_response if isinstance(baseline_response, dict) else {})
    search_seed_values = _extract_search_seed_values(baseline_response if isinstance(baseline_response, dict) else {})

    search_payloads = {
        "__no_match__": {
            **payload,
            "parameter": {**parameter, "Search": "__NO_SUCH_STORED_VALUE_DOC__"},
        }
    }
    for key, values in search_seed_values.items():
        for value in values:
            search_payloads[f"{key}:{value}"] = {
                **payload,
                "parameter": {**parameter, "Search": value},
            }

    happen_date = first_row_context.get("happen_date", "").split(" ")[0].replace("-", "")
    date_window_payloads = {}
    if happen_date:
        date_window_payloads["single_day_first_row"] = {
            **payload,
            "parameter": {**parameter, "BeginDate": happen_date, "EndDate": happen_date},
        }
    date_window_payloads["late_window"] = {
        **payload,
        "parameter": {**parameter, "BeginDate": "20260301", "EndDate": "20260401"},
    }
    partition_payloads = {}
    begin_date = str(parameter.get("BeginDate") or "").replace("-", "")
    end_date = str(parameter.get("EndDate") or "").replace("-", "")
    if len(begin_date) == 8 and len(end_date) == 8:
        for index, (begin_value, end_value) in enumerate(
            _build_quarterly_half_open_windows(begin_date, end_date),
            start=1,
        ):
            partition_payloads[f"quarter_{index}:{begin_value}_{end_value}"] = {
                **payload,
                "parameter": {
                    **parameter,
                    "BeginDate": begin_value,
                    "EndDate": end_value,
                },
            }

    search_responses = {key: curl_post_json(url, item, headers)[1] for key, item in search_payloads.items()}
    date_window_responses = {
        key: curl_post_json(url, item, headers)[1]
        for key, item in date_window_payloads.items()
    }
    partition_responses = {
        key: curl_post_json(url, item, headers)[1]
        for key, item in partition_payloads.items()
    }

    evidence = build_stored_value_http_evidence_chain(
        stored_value_baseline_payload=baseline_response,
        baseline_request_payload=parameter,
        stored_value_search_payloads=search_responses,
        stored_value_date_window_payloads=date_window_responses,
        stored_value_partition_payloads=partition_responses,
        date_partition_mode="half_open_end_date",
    )
    evidence["meta"] = {
        "generated_at": now_local().isoformat(),
        "timezone": str(LOCAL_TZ),
        "url": url,
        "request_payloads": {
            "baseline": payload,
            "search": search_payloads,
            "date_window": date_window_payloads,
            "date_partitions": partition_payloads,
        },
        "first_row_context": first_row_context,
        "search_seed_values": search_seed_values,
    }

    timestamp = now_local().strftime("%Y%m%d-%H%M%S")
    output_path = SAMPLES_DIR / "analysis" / f"stored-value-evidence-chain-{timestamp}.json"
    save_json(output_path, evidence)
    print(output_path.relative_to(PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
