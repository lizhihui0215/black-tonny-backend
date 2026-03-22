from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.member_evidence_service import build_member_http_evidence_chain
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


def _extract_rows(payload: dict) -> list[dict]:
    if isinstance(payload.get("retdata"), list) and payload["retdata"] and isinstance(payload["retdata"][0], dict):
        rows = payload["retdata"][0].get("Data")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    if isinstance(payload.get("retdata"), dict):
        rows = payload["retdata"].get("Data")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def main() -> int:
    auth = read_login_auth(README_PATH)
    access_token, _ = refresh_session_access_token(auth)

    spec = find_report_spec_by_title(REPORT_DOC_PATH, "会员中心")
    if spec is None:
        raise RuntimeError("未能在 report_api_samples.md 中找到“会员中心”样本")
    url = maybe_override_url(spec, auth.api_base_url)
    headers = build_report_auth_headers(url, access_token)

    baseline_payload = dict(spec.payload)
    _, baseline_response = curl_post_json(url, baseline_payload, headers)
    baseline_rows = _extract_rows(baseline_response)
    if not baseline_rows:
        raise RuntimeError("会员中心 baseline 未返回可分析数据")

    first_row = baseline_rows[0]
    exact_search_value = (
        str(first_row.get("VipCardID") or first_row.get("MobliePhone") or first_row.get("VipCode") or "").strip()
    )
    if not exact_search_value:
        raise RuntimeError("会员中心 baseline 缺少可用于 exact search probe 的字段")

    search_payloads = {
        "exact_search": {**baseline_payload, "searchval": exact_search_value},
        "broad_search": {**baseline_payload, "searchval": "1"},
        "no_match": {**baseline_payload, "searchval": "__codex_no_member_match__"},
    }
    search_responses = {
        key: curl_post_json(url, payload, headers)[1]
        for key, payload in search_payloads.items()
    }

    volume_payloads = {
        "1": {**baseline_payload, "VolumeNumber": "1"},
        "2": {**baseline_payload, "VolumeNumber": "2"},
        "10": {**baseline_payload, "VolumeNumber": "10"},
    }
    volume_responses = {
        key: curl_post_json(url, payload, headers)[1]
        for key, payload in volume_payloads.items()
    }

    condition_payloads = {
        "name": {**baseline_payload, "condition": "name", "searchval": "A"},
        "VipCode": {**baseline_payload, "condition": "VipCode", "searchval": first_row.get("VipCode", "")},
        "MobliePhone": {**baseline_payload, "condition": "MobliePhone", "searchval": first_row.get("MobliePhone", "")},
    }
    condition_responses = {
        key: curl_post_json(url, payload, headers)[1]
        for key, payload in condition_payloads.items()
    }

    evidence = build_member_http_evidence_chain(
        member_center_baseline_payload=baseline_response,
        member_center_search_payloads=search_responses,
        member_center_volume_payloads=volume_responses,
        member_center_condition_payloads=condition_responses,
    )
    evidence["meta"] = {
        "generated_at": now_local().isoformat(),
        "timezone": str(LOCAL_TZ),
        "report_title": spec.title,
        "url": url,
        "exact_search_value": exact_search_value,
        "sample_context": {
            "vip_code": first_row.get("VipCode"),
            "vip_card_id": first_row.get("VipCardID"),
            "mobile_phone": first_row.get("MobliePhone"),
        },
        "request_payloads": {
            "baseline": baseline_payload,
            "search": search_payloads,
            "volume": volume_payloads,
            "condition": condition_payloads,
        },
    }

    timestamp = now_local().strftime("%Y%m%d-%H%M%S")
    output_path = SAMPLES_DIR / "analysis" / f"member-evidence-chain-{timestamp}.json"
    save_json(output_path, evidence)
    print(output_path.relative_to(PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
