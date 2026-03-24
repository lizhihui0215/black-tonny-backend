#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.erp_research_service import extract_normalized_table_rows
from app.services.research.member_sales_rank_snapshot_evidence import (
    build_member_sales_rank_snapshot_http_evidence_chain,
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


def main() -> int:
    auth = read_login_auth(README_PATH)
    access_token, _ = refresh_session_access_token(auth)

    report_spec = find_report_spec_by_title(REPORT_DOC_PATH, "会员消费排行")
    if report_spec is None or not isinstance(report_spec.payload, dict):
        raise RuntimeError("未在 report_api_samples.md 中找到可用的 会员消费排行 payload")

    payload = dict(report_spec.payload)
    url = maybe_override_url(report_spec, auth.raw_login_data.get("EposApiUrl") if auth.raw_login_data else auth.api_base_url)
    headers = build_report_auth_headers(url, access_token)

    _, baseline_response = curl_post_json(url, payload, headers)

    page_probe_results = {}
    for page, pagesize in ((0, 20), (1, 20), (1, 0)):
        probe_payload = dict(payload)
        probe_payload["page"] = page
        probe_payload["pagesize"] = pagesize
        _, probe_response = curl_post_json(url, probe_payload, headers)
        page_probe_results[f"page_{page}_pagesize_{pagesize}_rows"] = len(extract_normalized_table_rows(probe_response))

    evidence = build_member_sales_rank_snapshot_http_evidence_chain(
        member_sales_rank_baseline_payload=baseline_response,
        baseline_request_payload=payload,
        page_probe_results=page_probe_results,
    )
    evidence["meta"] = {
        "generated_at": now_local().isoformat(),
        "timezone": str(LOCAL_TZ),
        "url": url,
        "request_payload": payload,
    }

    timestamp = now_local().strftime("%Y%m%d-%H%M%S")
    output_path = SAMPLES_DIR / "analysis" / f"member-sales-rank-snapshot-evidence-chain-{timestamp}.json"
    save_json(output_path, evidence)
    print(output_path.relative_to(PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
