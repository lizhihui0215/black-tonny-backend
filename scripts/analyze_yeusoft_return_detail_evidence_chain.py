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

from app.services.research.return_detail_evidence import (
    build_return_detail_base_info_filter_probes,
    build_return_detail_http_evidence_chain,
)
from scripts.fetch_yeusoft_report_payloads import (
    DEFAULT_SESSION_PATH,
    README_PATH,
    build_report_auth_headers,
    perform_request,
    persist_session_refresh,
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
STATIC_NARROW_FILTER_PROBES = {
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


def _fetch(
    url: str,
    payload: dict[str, object],
    *,
    access_token: str,
    transport: str,
) -> object:
    headers = build_report_auth_headers(url, access_token)
    status, response_payload = perform_request(transport, url, payload, headers)
    if status != 200:
        raise RuntimeError(f"{url} 请求失败，HTTP {status}")
    return response_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Yeusoft 退货明细 HTTP 证据链")
    parser.add_argument("--auth-source", choices=["auto", "login", "session"], default="login")
    parser.add_argument("--transport", choices=["curl", "urllib"], default="curl")
    parser.add_argument(
        "--type-values",
        default="0,1,2,3,4,5",
        help="逗号分隔的 type seed 值；会额外自动补 blank probe。默认也覆盖页面祖先状态里出现的 4/5 候选值",
    )
    parser.add_argument("--disable-derived-probes", action="store_true", help="关闭基于 ReturnStockBaseInfo 自动生成的过滤维度 probe")
    parser.add_argument("--output", help="输出 JSON 文件路径；默认写入 tmp/capture-samples/analysis")
    args = parser.parse_args()

    type_values = [item.strip() for item in args.type_values.split(",") if item.strip()]
    auth = resolve_auth_context(args.auth_source, README_PATH, DEFAULT_SESSION_PATH)
    access_token, refresh_expired_time = refresh_session_access_token(auth)
    if args.auth_source == "session" and DEFAULT_SESSION_PATH.exists():
        persist_session_refresh(auth, access_token, refresh_expired_time)

    base_info_payload = {"menuid": "E004003004"}
    baseline_payload = dict(RETURN_BASE_PAYLOAD)

    base_info_response = _fetch(
        RETURN_BASE_INFO_URL,
        base_info_payload,
        access_token=access_token,
        transport=args.transport,
    )
    auth_context = {
        "company_code": auth.company_code,
        "dept_code": auth.dept_code,
        "dept_name": auth.dept_name,
        "user_name": auth.user_name,
    }
    baseline_response = _fetch(
        RETURN_DETAIL_URL,
        baseline_payload,
        access_token=access_token,
        transport=args.transport,
    )
    type_payloads = {}
    type_probe_values = ["blank", *type_values]
    for value in type_probe_values:
        payload = dict(RETURN_BASE_PAYLOAD)
        if value != "blank":
            payload["type"] = value
        else:
            payload["type"] = ""
        response_payload = _fetch(
            RETURN_DETAIL_URL,
            payload,
            access_token=access_token,
            transport=args.transport,
        )
        type_payloads[value] = response_payload

    derived_filter_probes = (
        {}
        if args.disable_derived_probes
        else build_return_detail_base_info_filter_probes(base_info_response)
    )
    narrow_filter_probes = {**STATIC_NARROW_FILTER_PROBES, **derived_filter_probes}
    narrow_filter_payloads = {}
    for name, overrides in narrow_filter_probes.items():
        payload = {**RETURN_BASE_PAYLOAD, **overrides}
        response_payload = _fetch(
            RETURN_DETAIL_URL,
            payload,
            access_token=access_token,
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
            "type_values": type_probe_values,
            "narrow_filter_probes": narrow_filter_probes,
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
