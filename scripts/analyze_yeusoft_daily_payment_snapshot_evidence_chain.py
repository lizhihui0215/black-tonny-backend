#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.research.daily_payment_snapshot_evidence import (
    build_daily_payment_snapshot_http_evidence_chain,
)
from app.services.erp_research_service import analyze_response_payload
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


SEARCHTYPE_SEEDS = ("", "1", "2", "3", "4", "5")


def main() -> int:
    auth = read_login_auth(README_PATH)
    access_token, _ = refresh_session_access_token(auth)

    report_spec = find_report_spec_by_title(REPORT_DOC_PATH, "每日流水单")
    if report_spec is None or not isinstance(report_spec.payload, dict):
        raise RuntimeError("未在 report_api_samples.md 中找到可用的 每日流水单 payload")

    payload = dict(report_spec.payload)
    url = maybe_override_url(report_spec, auth.raw_login_data.get("JyApiUrl") if auth.raw_login_data else auth.api_base_url)
    headers = build_report_auth_headers(url, access_token)

    _, baseline_response = curl_post_json(url, payload, headers)
    baseline_analysis = analyze_response_payload(baseline_response)
    baseline_signature = str(baseline_analysis.get("row_set_signature") or "")

    searchtype_seed_results: dict[str, dict[str, object]] = {}
    for seed in SEARCHTYPE_SEEDS:
        seed_payload = dict(payload)
        seed_payload["SearchType"] = seed
        status, seed_response = curl_post_json(url, seed_payload, headers)
        seed_analysis = analyze_response_payload(seed_response)
        semantics = "error"
        if status == 200 and not seed_analysis.get("error_code"):
            semantics = (
                "same_dataset"
                if str(seed_analysis.get("row_set_signature") or "") == baseline_signature
                else "different_dataset"
            )
        searchtype_seed_results[str(seed)] = {
            "status": status,
            "response_shape": seed_analysis.get("response_shape"),
            "row_count": seed_analysis.get("row_count"),
            "row_set_signature": seed_analysis.get("row_set_signature"),
            "error_code": seed_analysis.get("error_code"),
            "error_message": seed_analysis.get("error_message"),
            "semantics": semantics,
        }

    evidence = build_daily_payment_snapshot_http_evidence_chain(
        daily_payment_baseline_payload=baseline_response,
        baseline_request_payload=payload,
        searchtype_seed_results=searchtype_seed_results,
    )
    evidence["meta"] = {
        "generated_at": now_local().isoformat(),
        "timezone": str(LOCAL_TZ),
        "url": url,
        "request_payload": payload,
    }

    timestamp = now_local().strftime("%Y%m%d-%H%M%S")
    output_path = SAMPLES_DIR / "analysis" / f"daily-payment-snapshot-evidence-chain-{timestamp}.json"
    save_json(output_path, evidence)
    print(output_path.relative_to(PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
