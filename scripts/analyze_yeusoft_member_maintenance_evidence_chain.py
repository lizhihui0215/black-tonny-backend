from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.research.member_maintenance_evidence import (  # noqa: E402
    build_member_maintenance_http_evidence_chain,
)
from scripts.fetch_yeusoft_report_payloads import (  # noqa: E402
    LOCAL_TZ,
    README_PATH,
    SAMPLES_DIR,
    build_report_auth_headers,
    curl_post_json,
    now_local,
    read_login_auth,
    refresh_session_access_token,
    save_json,
)


MEMBER_MAINTENANCE_URL = "https://erpapistaging.yeusoft.net/eposapi/YisEposVipReturnVisit/SelVipReturnVisitList"


def main() -> int:
    auth = read_login_auth(README_PATH)
    access_token, _ = refresh_session_access_token(auth)
    headers = build_report_auth_headers(MEMBER_MAINTENANCE_URL, access_token)

    baseline_payload = {
        "search": "",
        "brdate": "",
        "erdate": "",
        "bdate": "",
        "edate": "",
        "type": "",
        "page": 1,
        "pagesize": 20,
    }

    page_payloads = {
        "page=2,pagesize=20": {**baseline_payload, "page": 2},
        "page=3,pagesize=20": {**baseline_payload, "page": 3},
    }
    pagesize_payloads = {
        "page=1,pagesize=50": {**baseline_payload, "pagesize": 50},
        "page=1,pagesize=5000": {**baseline_payload, "pagesize": 5000},
    }
    search_payloads = {
        "__no_match__": {**baseline_payload, "search": "__codex_no_member_maintenance_match__"},
        "blank": {**baseline_payload, "search": ""},
    }
    type_payloads = {
        "消费回访": {**baseline_payload, "type": "消费回访"},
        "其他回访": {**baseline_payload, "type": "其他回访"},
    }
    bdate_payloads = {
        "bdate=20260323,edate=20260323": {**baseline_payload, "bdate": "20260323", "edate": "20260323"},
        "bdate=20260301,edate=20260323": {**baseline_payload, "bdate": "20260301", "edate": "20260323"},
    }
    brdate_payloads = {
        "brdate=20260323,erdate=20260323": {**baseline_payload, "brdate": "20260323", "erdate": "20260323"},
        "brdate=20260301,erdate=20260323": {**baseline_payload, "brdate": "20260301", "erdate": "20260323"},
    }

    _, baseline_response = curl_post_json(MEMBER_MAINTENANCE_URL, baseline_payload, headers)
    page_responses = {key: curl_post_json(MEMBER_MAINTENANCE_URL, payload, headers)[1] for key, payload in page_payloads.items()}
    pagesize_responses = {
        key: curl_post_json(MEMBER_MAINTENANCE_URL, payload, headers)[1]
        for key, payload in pagesize_payloads.items()
    }
    search_responses = {
        key: curl_post_json(MEMBER_MAINTENANCE_URL, payload, headers)[1]
        for key, payload in search_payloads.items()
    }
    type_responses = {
        key: curl_post_json(MEMBER_MAINTENANCE_URL, payload, headers)[1]
        for key, payload in type_payloads.items()
    }
    bdate_responses = {
        key: curl_post_json(MEMBER_MAINTENANCE_URL, payload, headers)[1]
        for key, payload in bdate_payloads.items()
    }
    brdate_responses = {
        key: curl_post_json(MEMBER_MAINTENANCE_URL, payload, headers)[1]
        for key, payload in brdate_payloads.items()
    }

    evidence = build_member_maintenance_http_evidence_chain(
        member_maintenance_baseline_payload=baseline_response,
        member_maintenance_page_payloads=page_responses,
        member_maintenance_pagesize_payloads=pagesize_responses,
        member_maintenance_search_payloads=search_responses,
        member_maintenance_type_payloads=type_responses,
        member_maintenance_bdate_payloads=bdate_responses,
        member_maintenance_brdate_payloads=brdate_responses,
    )
    evidence["meta"] = {
        "generated_at": now_local().isoformat(),
        "timezone": str(LOCAL_TZ),
        "url": MEMBER_MAINTENANCE_URL,
        "request_payloads": {
            "baseline": baseline_payload,
            "page": page_payloads,
            "pagesize": pagesize_payloads,
            "search": search_payloads,
            "type": type_payloads,
            "bdate_edate": bdate_payloads,
            "brdate_erdate": brdate_payloads,
        },
    }

    timestamp = now_local().strftime("%Y%m%d-%H%M%S")
    output_path = SAMPLES_DIR / "analysis" / f"member-maintenance-evidence-chain-{timestamp}.json"
    save_json(output_path, evidence)
    print(output_path.relative_to(PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
