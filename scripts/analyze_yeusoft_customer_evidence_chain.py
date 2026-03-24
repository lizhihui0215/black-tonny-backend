from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.research.customer_evidence import build_customer_http_evidence_chain
from scripts.fetch_yeusoft_report_payloads import (
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


CUSTOMER_URL = "https://erpapistaging.yeusoft.net/eposapi/YisEposDeptClientSet/SelDeptList"


def main() -> int:
    auth = read_login_auth(README_PATH)
    access_token, _ = refresh_session_access_token(auth)
    headers = build_report_auth_headers(CUSTOMER_URL, access_token)

    baseline_payload = {
        "deptname": "",
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
        "__no_match__": {**baseline_payload, "deptname": "__codex_no_customer_match__"},
        "blank": {**baseline_payload, "deptname": ""},
    }

    _, baseline_response = curl_post_json(CUSTOMER_URL, baseline_payload, headers)
    page_responses = {key: curl_post_json(CUSTOMER_URL, payload, headers)[1] for key, payload in page_payloads.items()}
    pagesize_responses = {
        key: curl_post_json(CUSTOMER_URL, payload, headers)[1]
        for key, payload in pagesize_payloads.items()
    }
    search_responses = {
        key: curl_post_json(CUSTOMER_URL, payload, headers)[1]
        for key, payload in search_payloads.items()
    }

    evidence = build_customer_http_evidence_chain(
        customer_baseline_payload=baseline_response,
        customer_page_payloads=page_responses,
        customer_pagesize_payloads=pagesize_responses,
        customer_search_payloads=search_responses,
    )
    evidence["meta"] = {
        "generated_at": now_local().isoformat(),
        "timezone": str(LOCAL_TZ),
        "url": CUSTOMER_URL,
        "request_payloads": {
            "baseline": baseline_payload,
            "page": page_payloads,
            "pagesize": pagesize_payloads,
            "deptname": search_payloads,
        },
    }

    timestamp = now_local().strftime("%Y%m%d-%H%M%S")
    output_path = SAMPLES_DIR / "analysis" / f"customer-evidence-chain-{timestamp}.json"
    save_json(output_path, evidence)
    print(output_path.relative_to(PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
