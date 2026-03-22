from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.inventory_evidence_service import build_inventory_http_evidence_chain
from scripts.fetch_yeusoft_report_payloads import (
    DEFAULT_SESSION_PATH,
    README_PATH,
    REPORT_DOC_PATH,
    build_report_auth_headers,
    find_report_spec_by_title,
    maybe_override_url,
    perform_request,
    refresh_session_access_token,
    resolve_auth_context,
)

LOCAL_TZ = ZoneInfo("Asia/Shanghai")
OUTPUT_ROOT = PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"


def now_local() -> datetime:
    return datetime.now(LOCAL_TZ)


def _clone_payload(payload):
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _set_payload_value(payload, key: str, value):
    copied = _clone_payload(payload)
    copied[key] = value
    return copied


def _first_csv_token(value) -> str | None:
    if not isinstance(value, str):
        return None
    token = next((item.strip() for item in value.split(",") if item.strip()), "")
    return token or None


def _csv_tokens(value) -> list[str]:
    if not isinstance(value, str):
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _fetch_report(*, auth_source: str, title: str, payload_override: dict | None = None, transport: str = "curl"):
    auth = resolve_auth_context(auth_source, README_PATH, DEFAULT_SESSION_PATH)
    access_token, refresh_expired_time = refresh_session_access_token(auth)
    if auth_source == "session" and DEFAULT_SESSION_PATH.exists():
        from scripts.fetch_yeusoft_report_payloads import persist_session_refresh

        persist_session_refresh(auth, access_token, refresh_expired_time)
    spec = find_report_spec_by_title(REPORT_DOC_PATH, title)
    if spec is None:
        raise RuntimeError(f"未找到报表样本：{title}")
    payload = payload_override if payload_override is not None else _clone_payload(spec.payload)
    url = maybe_override_url(spec, auth.api_base_url)
    headers = build_report_auth_headers(url, access_token)
    status, response_payload = perform_request(transport, url, payload, headers)
    if status != 200:
        raise RuntimeError(f"{title} 请求失败，HTTP {status}")
    return {
        "title": title,
        "url": url,
        "payload": payload,
        "response": response_payload,
        "auth_context": {
            "company_code": auth.company_code,
            "dept_code": auth.dept_code,
            "dept_name": auth.dept_name,
            "user_name": auth.user_name,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Yeusoft 库存主线 HTTP 证据链")
    parser.add_argument("--auth-source", choices=["auto", "login", "session"], default="login")
    parser.add_argument("--transport", choices=["curl", "urllib"], default="curl")
    parser.add_argument("--output", help="输出 JSON 文件路径；默认写入 tmp/capture-samples/analysis")
    args = parser.parse_args()

    inventory_spec = find_report_spec_by_title(REPORT_DOC_PATH, "库存明细统计")
    outin_spec = find_report_spec_by_title(REPORT_DOC_PATH, "出入库单据")
    if inventory_spec is None or outin_spec is None:
        raise RuntimeError("缺少库存明细统计或出入库单据样本定义")

    inventory_baseline_payload = _clone_payload(inventory_spec.payload)
    outin_baseline_payload = _clone_payload(outin_spec.payload)
    page_baseline_payload = _set_payload_value(_set_payload_value(inventory_baseline_payload, "page", 0), "pagesize", 20)

    inventory_baseline = _fetch_report(
        auth_source=args.auth_source,
        title="库存明细统计",
        payload_override=page_baseline_payload,
        transport=args.transport,
    )
    inventory_stockflag_payloads = {
        value: _fetch_report(
            auth_source=args.auth_source,
            title="库存明细统计",
            payload_override=_set_payload_value(page_baseline_payload, "stockflag", value),
            transport=args.transport,
        )["response"]
        for value in ("0", "1", "2")
    }
    inventory_page_payloads = {
        value: _fetch_report(
            auth_source=args.auth_source,
            title="库存明细统计",
            payload_override=_set_payload_value(
                _set_payload_value(page_baseline_payload, "stockflag", value),
                "page",
                1,
            ),
            transport=args.transport,
        )["response"]
        for value in ("0", "1", "2")
    }

    type_tokens = _csv_tokens(outin_baseline_payload.get("type"))
    doctype_tokens = _csv_tokens(outin_baseline_payload.get("doctype"))
    outin_baseline = _fetch_report(
        auth_source=args.auth_source,
        title="出入库单据",
        payload_override=outin_baseline_payload,
        transport=args.transport,
    )
    outin_datetype_payloads = {
        value: _fetch_report(
            auth_source=args.auth_source,
            title="出入库单据",
            payload_override=_set_payload_value(outin_baseline_payload, "datetype", value),
            transport=args.transport,
        )["response"]
        for value in ("1", "2")
    }
    outin_type_payloads = {
        value: _fetch_report(
            auth_source=args.auth_source,
            title="出入库单据",
            payload_override=_set_payload_value(outin_baseline_payload, "type", value),
            transport=args.transport,
        )["response"]
        for value in type_tokens
        if value
    }
    outin_doctype_payloads = {
        value: _fetch_report(
            auth_source=args.auth_source,
            title="出入库单据",
            payload_override=_set_payload_value(outin_baseline_payload, "doctype", value),
            transport=args.transport,
        )["response"]
        for value in doctype_tokens
        if value
    }

    result = build_inventory_http_evidence_chain(
        inventory_detail_baseline_payload=inventory_baseline["response"],
        inventory_detail_stockflag_payloads=inventory_stockflag_payloads,
        inventory_detail_page_payloads=inventory_page_payloads,
        outin_baseline_payload=outin_baseline["response"],
        outin_datetype_payloads=outin_datetype_payloads,
        outin_type_payloads=outin_type_payloads,
        outin_doctype_payloads=outin_doctype_payloads,
    )
    result["generated_at"] = now_local().isoformat()
    result["auth_context"] = inventory_baseline["auth_context"]
    result["requests"] = {
        "inventory_detail": {
            "baseline": {"payload": inventory_baseline["payload"], "url": inventory_baseline["url"]},
            "stockflag_values": list(inventory_stockflag_payloads.keys()),
            "page_payloads_by_stockflag": {
                key: {"page": 1, "stockflag": key, "pagesize": page_baseline_payload.get("pagesize", 20)}
                for key in inventory_page_payloads
            },
        },
        "outin_report": {
            "baseline": {"payload": outin_baseline["payload"], "url": outin_baseline["url"]},
            "datetype_values": list(outin_datetype_payloads.keys()),
            "type_values": list(outin_type_payloads.keys()),
            "doctype_values": list(outin_doctype_payloads.keys()),
        },
    }

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = OUTPUT_ROOT / f"inventory-evidence-chain-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({"ok": True, "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
