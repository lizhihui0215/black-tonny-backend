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

from app.services.research.store_stocktaking_evidence import (
    build_store_stocktaking_http_evidence_chain,
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
STORE_STOCKTAKING_URL = "https://jyapistaging.yeusoft.net/JyApi/EposDoc/SelDocManageList"
BASELINE_PAYLOAD = {
    "edate": "20260323",
    "bdate": "20260316",
    "deptcode": "",
    "stat": "A",
    "menuid": "E003002001",
}


def now_local() -> datetime:
    return datetime.now(LOCAL_TZ)


def _fetch(payload: dict[str, object], *, auth_source: str, transport: str) -> tuple[object, dict[str, str]]:
    auth = resolve_auth_context(auth_source, README_PATH, DEFAULT_SESSION_PATH)
    access_token, refresh_expired_time = refresh_session_access_token(auth)
    if auth_source == "session" and DEFAULT_SESSION_PATH.exists():
        from scripts.fetch_yeusoft_report_payloads import persist_session_refresh

        persist_session_refresh(auth, access_token, refresh_expired_time)
    headers = build_report_auth_headers(STORE_STOCKTAKING_URL, access_token)
    status, response_payload = perform_request(transport, STORE_STOCKTAKING_URL, payload, headers)
    if status != 200:
        raise RuntimeError(f"{STORE_STOCKTAKING_URL} 请求失败，HTTP {status}")
    return response_payload, {
        "company_code": auth.company_code,
        "dept_code": auth.dept_code,
        "dept_name": auth.dept_name,
        "user_name": auth.user_name,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Yeusoft 门店盘点单 HTTP 证据链")
    parser.add_argument("--auth-source", choices=["auto", "login", "session"], default="login")
    parser.add_argument("--transport", choices=["curl", "urllib"], default="curl")
    parser.add_argument("--output", help="输出 JSON 文件路径；默认写入 tmp/capture-samples/analysis")
    args = parser.parse_args()

    baseline_response, auth_context = _fetch(BASELINE_PAYLOAD, auth_source=args.auth_source, transport=args.transport)
    stat_payloads = {
        "stat=A": BASELINE_PAYLOAD,
        "stat=0": {**BASELINE_PAYLOAD, "stat": "0"},
        "stat=1": {**BASELINE_PAYLOAD, "stat": "1"},
    }
    date_payloads = {
        "bdate=20260316,edate=20260323": BASELINE_PAYLOAD,
        "bdate=20260323,edate=20260323": {**BASELINE_PAYLOAD, "bdate": "20260323"},
    }

    def _collect(payloads: dict[str, dict[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, payload in payloads.items():
            response_payload, _ = _fetch(payload, auth_source=args.auth_source, transport=args.transport)
            result[key] = response_payload
        return result

    result = build_store_stocktaking_http_evidence_chain(
        baseline_payload=baseline_response,
        stat_payloads=_collect(stat_payloads),
        date_payloads=_collect(date_payloads),
    )
    result["generated_at"] = now_local().isoformat()
    result["auth_context"] = auth_context
    result["requests"] = {
        "baseline": {"url": STORE_STOCKTAKING_URL, "payload": BASELINE_PAYLOAD},
        "stat_payloads": stat_payloads,
        "date_payloads": date_payloads,
    }

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = OUTPUT_ROOT / f"store-stocktaking-evidence-chain-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({"ok": True, "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
