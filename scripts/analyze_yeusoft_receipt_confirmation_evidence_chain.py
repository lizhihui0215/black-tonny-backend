from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.erp_research_service import extract_normalized_table_rows
from app.services.research.receipt_confirmation_evidence import (
    build_receipt_confirmation_http_evidence_chain,
)
from scripts.fetch_yeusoft_report_payloads import (
    DEFAULT_SESSION_PATH,
    README_PATH,
    build_report_auth_headers,
    perform_request,
    refresh_session_access_token,
    resolve_auth_context,
)

LOCAL_TZ = ZoneInfo("Asia/Shanghai")
OUTPUT_ROOT = PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"
RECEIPT_CONFIRMATION_URL = "https://jyapistaging.yeusoft.net/JyApi/EposDoc/SelDocConfirmList"


def now_local() -> datetime:
    return datetime.now(LOCAL_TZ)


def _fetch(payload: dict[str, object], *, auth_source: str, transport: str) -> tuple[object, dict[str, str]]:
    auth = resolve_auth_context(auth_source, README_PATH, DEFAULT_SESSION_PATH)
    access_token, refresh_expired_time = refresh_session_access_token(auth)
    if auth_source == "session" and DEFAULT_SESSION_PATH.exists():
        from scripts.fetch_yeusoft_report_payloads import persist_session_refresh

        persist_session_refresh(auth, access_token, refresh_expired_time)
    headers = build_report_auth_headers(RECEIPT_CONFIRMATION_URL, access_token)
    status, response_payload = perform_request(transport, RECEIPT_CONFIRMATION_URL, payload, headers)
    if status != 200:
        raise RuntimeError(f"{RECEIPT_CONFIRMATION_URL} 请求失败，HTTP {status}")
    return response_payload, {
        "company_code": auth.company_code,
        "dept_code": auth.dept_code,
        "dept_name": auth.dept_name,
        "user_name": auth.user_name,
    }


def _derive_search_doc_no(baseline_payload: object) -> str | None:
    for row in extract_normalized_table_rows(baseline_payload):
        value = row.get("docno") or row.get("doc_no")
        if value not in (None, ""):
            return str(value)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Yeusoft 收货确认 HTTP 证据链")
    parser.add_argument("--auth-source", choices=["auto", "login", "session"], default="login")
    parser.add_argument("--transport", choices=["curl", "urllib"], default="curl")
    parser.add_argument("--time-value", help="time probe 的日期值，默认使用当天 YYYYMMDD")
    parser.add_argument("--output", help="输出 JSON 文件路径；默认写入 tmp/capture-samples/analysis")
    args = parser.parse_args()

    baseline_response, auth_context = _fetch({}, auth_source=args.auth_source, transport=args.transport)
    doc_no = _derive_search_doc_no(baseline_response)
    time_value = args.time_value or now_local().strftime("%Y%m%d")

    page_payloads = {
        "page=1,pagesize=20": {"page": 1, "pageSize": 20},
        "page=2,pagesize=20": {"page": 2, "pageSize": 20},
    }
    page_size_payloads = {
        "page=1,pagesize=20": {"page": 1, "pageSize": 20},
        "page=1,pagesize=5000": {"page": 1, "pageSize": 5000},
    }
    time_payloads = {
        f"time={time_value}": {"time": time_value},
        "time=''": {"time": ""},
    }
    search_payloads = {"__no_match__": {"search": "__NO_SUCH_DOC__"}}
    if doc_no:
        search_payloads[f"search={doc_no}"] = {"search": doc_no}

    def _collect(payloads: dict[str, dict[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, payload in payloads.items():
            response_payload, _ = _fetch(payload, auth_source=args.auth_source, transport=args.transport)
            result[key] = response_payload
        return result

    result = build_receipt_confirmation_http_evidence_chain(
        baseline_payload=baseline_response,
        page_payloads=_collect(page_payloads),
        page_size_payloads=_collect(page_size_payloads),
        time_payloads=_collect(time_payloads),
        search_payloads=_collect(search_payloads),
    )
    result["generated_at"] = now_local().isoformat()
    result["auth_context"] = auth_context
    result["requests"] = {
        "baseline": {"url": RECEIPT_CONFIRMATION_URL, "payload": {}},
        "page_payloads": page_payloads,
        "page_size_payloads": page_size_payloads,
        "time_payloads": time_payloads,
        "search_payloads": search_payloads,
    }

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = OUTPUT_ROOT / f"receipt-confirmation-evidence-chain-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({"ok": True, "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
