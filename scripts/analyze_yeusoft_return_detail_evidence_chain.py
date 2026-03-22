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

from app.services.return_detail_evidence_service import build_return_detail_http_evidence_chain
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
RETURN_BASE_INFO_URL = "https://erpapistaging.yeusoft.net/eposapi/YisEposReport/ReturnStockBaseInfo"
RETURN_DETAIL_URL = "https://erpapistaging.yeusoft.net/eposapi/YisEposReport/SelReturnStockList"
RETURN_BASE_PAYLOAD = {
    "menuid": "E004003004",
    "gridid": "E004003004_2",
    "warecause": "",
    "spenum": "",
}
DEFAULT_NARROW_FILTER_PROBES = {
    "TrademarkCode=01": {"TrademarkCode": "01"},
    "Years=2026": {"Years": "2026"},
    "Season=1": {"Season": "1"},
    "PlatId=1": {"PlatId": "1"},
    "Order=1": {"Order": "1"},
    "ArriveStore=1": {"ArriveStore": "1"},
    "TrademarkCode=01,Years=2026": {"TrademarkCode": "01", "Years": "2026"},
}


def now_local() -> datetime:
    return datetime.now(LOCAL_TZ)


def _fetch(url: str, payload: dict[str, object], *, auth_source: str, transport: str) -> tuple[object, dict[str, str]]:
    auth = resolve_auth_context(auth_source, README_PATH, DEFAULT_SESSION_PATH)
    access_token, refresh_expired_time = refresh_session_access_token(auth)
    if auth_source == "session" and DEFAULT_SESSION_PATH.exists():
        from scripts.fetch_yeusoft_report_payloads import persist_session_refresh

        persist_session_refresh(auth, access_token, refresh_expired_time)
    headers = build_report_auth_headers(url, access_token)
    status, response_payload = perform_request(transport, url, payload, headers)
    if status != 200:
        raise RuntimeError(f"{url} 请求失败，HTTP {status}")
    return response_payload, {
        "company_code": auth.company_code,
        "dept_code": auth.dept_code,
        "dept_name": auth.dept_name,
        "user_name": auth.user_name,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Yeusoft 退货明细 HTTP 证据链")
    parser.add_argument("--auth-source", choices=["auto", "login", "session"], default="login")
    parser.add_argument("--transport", choices=["curl", "urllib"], default="curl")
    parser.add_argument("--type-values", default="0,1,2,3", help="逗号分隔的 type seed 值")
    parser.add_argument("--output", help="输出 JSON 文件路径；默认写入 tmp/capture-samples/analysis")
    args = parser.parse_args()

    type_values = [item.strip() for item in args.type_values.split(",") if item.strip()]
    base_info_payload = {"menuid": "E004003004"}
    baseline_payload = {**RETURN_BASE_PAYLOAD, "type": type_values[0] if type_values else "0"}

    base_info_response, auth_context = _fetch(
        RETURN_BASE_INFO_URL,
        base_info_payload,
        auth_source=args.auth_source,
        transport=args.transport,
    )
    baseline_response, _ = _fetch(
        RETURN_DETAIL_URL,
        baseline_payload,
        auth_source=args.auth_source,
        transport=args.transport,
    )
    type_payloads = {}
    for value in type_values:
        payload = {**RETURN_BASE_PAYLOAD, "type": value}
        response_payload, _ = _fetch(
            RETURN_DETAIL_URL,
            payload,
            auth_source=args.auth_source,
            transport=args.transport,
        )
        type_payloads[value] = response_payload

    narrow_filter_payloads = {}
    for name, overrides in DEFAULT_NARROW_FILTER_PROBES.items():
        payload = {**RETURN_BASE_PAYLOAD, "type": type_values[0] if type_values else "0", **overrides}
        response_payload, _ = _fetch(
            RETURN_DETAIL_URL,
            payload,
            auth_source=args.auth_source,
            transport=args.transport,
        )
        narrow_filter_payloads[name] = response_payload

    result = build_return_detail_http_evidence_chain(
        base_info_payload=base_info_response,
        baseline_payload=baseline_response,
        type_payloads=type_payloads,
        narrow_filter_payloads=narrow_filter_payloads,
    )
    result["generated_at"] = now_local().isoformat()
    result["auth_context"] = auth_context
    result["requests"] = {
        "base_info": {"url": RETURN_BASE_INFO_URL, "payload": base_info_payload},
        "return_detail": {
            "url": RETURN_DETAIL_URL,
            "baseline_payload": baseline_payload,
            "type_values": type_values,
            "narrow_filter_probes": DEFAULT_NARROW_FILTER_PROBES,
        },
    }

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = OUTPUT_ROOT / f"return-detail-evidence-chain-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({"ok": True, "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
