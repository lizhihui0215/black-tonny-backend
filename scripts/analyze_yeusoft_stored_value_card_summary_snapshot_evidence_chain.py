#!/usr/bin/env python3
from __future__ import annotations

import copy
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.erp_research_service import extract_normalized_table_rows
from app.services.research.stored_value_summary_snapshot_evidence import (
    build_stored_value_card_summary_snapshot_http_evidence_chain,
)
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


def _clone_payload(payload: dict[str, object]) -> dict[str, object]:
    return copy.deepcopy(payload)


def _probe_page_rows(
    url: str,
    headers: dict[str, str],
    payload: dict[str, object],
    *,
    page: int,
    pagesize: int,
) -> int:
    probe_payload = _clone_payload(payload)
    probe_payload["page"] = page
    probe_payload["pagesize"] = pagesize
    _, probe_response = curl_post_json(url, probe_payload, headers)
    return len(extract_normalized_table_rows(probe_response))


def _probe_search_rows(
    url: str,
    headers: dict[str, str],
    payload: dict[str, object],
    *,
    search_value: str,
) -> int:
    probe_payload = _clone_payload(payload)
    parameter = dict(probe_payload.get("parameter") or {})
    parameter["Search"] = search_value
    probe_payload["parameter"] = parameter
    _, probe_response = curl_post_json(url, probe_payload, headers)
    return len(extract_normalized_table_rows(probe_response))


def _first_card_search_seed(rows: list[dict[str, object]]) -> str | None:
    candidate_keys = (
        "VipCardID",
        "VipCardId",
        "VipCardNo",
        "CardNo",
        "会员卡号",
        "卡号",
    )
    for row in rows:
        for key in candidate_keys:
            value = row.get(key)
            if value not in (None, ""):
                return str(value)
    return None


def main() -> int:
    auth = read_login_auth(README_PATH)
    access_token, _ = refresh_session_access_token(auth)

    report_spec = find_report_spec_by_title(REPORT_DOC_PATH, "储值卡汇总")
    if report_spec is None or not isinstance(report_spec.payload, dict):
        raise RuntimeError("未在 report_api_samples.md 中找到可用的 储值卡汇总 payload")

    payload = dict(report_spec.payload)
    url = maybe_override_url(report_spec, auth.raw_login_data.get("EposApiUrl") if auth.raw_login_data else auth.api_base_url)
    headers = build_report_auth_headers(url, access_token)

    _, baseline_response = curl_post_json(url, payload, headers)
    baseline_rows = extract_normalized_table_rows(baseline_response)
    baseline_row_count = len(baseline_rows)

    page_probe_results = {}
    for page, pagesize in ((0, 20), (1, 20), (1, 0)):
        page_probe_results[f"page_{page}_pagesize_{pagesize}_rows"] = _probe_page_rows(
            url,
            headers,
            payload,
            page=page,
            pagesize=pagesize,
        )

    search_seed_results: dict[str, dict[str, object]] = {}
    for label, value in (("__no_match__", "__no_match__"),):
        rows = _probe_search_rows(url, headers, payload, search_value=value)
        search_seed_results[label] = {
            "rows": rows,
            "semantics": "same_dataset" if rows == baseline_row_count else "different_dataset",
        }
    first_card = _first_card_search_seed(baseline_rows)
    if first_card:
        rows = _probe_search_rows(url, headers, payload, search_value=first_card)
        search_seed_results[f"vip_card:{first_card}"] = {
            "rows": rows,
            "semantics": "same_dataset" if rows == baseline_row_count else "different_dataset",
        }

    evidence = build_stored_value_card_summary_snapshot_http_evidence_chain(
        stored_value_card_summary_baseline_payload=baseline_response,
        baseline_request_payload=payload,
        page_probe_results=page_probe_results,
        search_seed_results=search_seed_results,
    )
    evidence["meta"] = {
        "generated_at": now_local().isoformat(),
        "timezone": str(LOCAL_TZ),
        "url": url,
        "request_payload": payload,
    }

    timestamp = now_local().strftime("%Y%m%d-%H%M%S")
    output_path = SAMPLES_DIR / "analysis" / f"stored-value-card-summary-snapshot-evidence-chain-{timestamp}.json"
    save_json(output_path, evidence)
    print(output_path.relative_to(PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
