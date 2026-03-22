#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.product_evidence_service import build_product_http_evidence_chain
from scripts.fetch_yeusoft_report_payloads import (
    README_PATH,
    build_report_auth_headers,
    now_local,
    perform_request,
    read_login_auth,
    refresh_session_access_token,
)


PRODUCT_URL = "https://erpapistaging.yeusoft.net/eposapi/YisEposWareList/SelWareList"
BASELINE_PAYLOAD = {
    "spenum": "",
    "warecause": "",
    "page": 1,
    "pagesize": 60,
}
PAGE_PROBES = {
    "2": {"spenum": "", "warecause": "", "page": 2, "pagesize": 60},
}
PAGESIZE_PROBES = {
    "60": {"spenum": "", "warecause": "", "page": 1, "pagesize": 60},
    "100": {"spenum": "", "warecause": "", "page": 1, "pagesize": 100},
    "200": {"spenum": "", "warecause": "", "page": 1, "pagesize": 200},
    "500": {"spenum": "", "warecause": "", "page": 1, "pagesize": 500},
    "1000": {"spenum": "", "warecause": "", "page": 1, "pagesize": 1000},
    "2000": {"spenum": "", "warecause": "", "page": 1, "pagesize": 2000},
    "5000": {"spenum": "", "warecause": "", "page": 1, "pagesize": 5000},
}
BROAD_SPENUM_PROBES = {
    "TN": {"spenum": "TN", "warecause": "", "page": 1, "pagesize": 60},
    "TOX1": {"spenum": "TOX1", "warecause": "", "page": 1, "pagesize": 60},
}


def _extract_exact_codes(payload: object, *, limit: int = 3) -> list[str]:
    if not isinstance(payload, dict):
        return []
    retdata = payload.get("retdata")
    if not isinstance(retdata, list) or not retdata:
        return []
    first = retdata[0]
    if not isinstance(first, dict):
        return []
    rows = first.get("Data")
    if not isinstance(rows, list):
        return []
    codes: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get("SpeNum") or "").strip()
        if code and code not in codes:
            codes.append(code)
        if len(codes) >= limit:
            break
    return codes


def _request_payloads(
    transport: str,
    url: str,
    headers: dict[str, str],
    probes: dict[str, dict[str, object]],
) -> dict[str, object]:
    results: dict[str, object] = {}
    for key, payload in probes.items():
        status, body = perform_request(transport, url, payload, headers)
        if status != 200:
            raise RuntimeError(f"{url} {key} 返回 HTTP {status}")
        results[key] = body
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="分析 Yeusoft 商品资料的 HTTP evidence 链。")
    parser.add_argument("--readme", default=str(README_PATH))
    parser.add_argument("--transport", choices=["curl", "urllib"], default="curl")
    parser.add_argument(
        "--output",
        help="输出 evidence JSON；默认写入 tmp/capture-samples/analysis/product-evidence-chain-<timestamp>.json",
    )
    args = parser.parse_args()

    output_path = (
        Path(args.output)
        if args.output
        else PROJECT_ROOT
        / "tmp"
        / "capture-samples"
        / "analysis"
        / f"product-evidence-chain-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    )

    auth = read_login_auth(Path(args.readme))
    access_token, _ = refresh_session_access_token(auth)
    headers = build_report_auth_headers(PRODUCT_URL, access_token)

    status, baseline_payload = perform_request(args.transport, PRODUCT_URL, dict(BASELINE_PAYLOAD), headers)
    if status != 200:
        raise RuntimeError(f"商品资料 baseline 返回 HTTP {status}")

    page_payloads = _request_payloads(args.transport, PRODUCT_URL, headers, PAGE_PROBES)
    pagesize_payloads = _request_payloads(args.transport, PRODUCT_URL, headers, PAGESIZE_PROBES)
    exact_codes = _extract_exact_codes(baseline_payload)
    exact_probes = {
        code: {"spenum": code, "warecause": "", "page": 1, "pagesize": 60}
        for code in exact_codes
    }
    spenum_payloads = _request_payloads(
        args.transport,
        PRODUCT_URL,
        headers,
        {**BROAD_SPENUM_PROBES, **exact_probes},
    )

    evidence = build_product_http_evidence_chain(
        product_baseline_payload=baseline_payload,
        product_page_payloads=page_payloads,
        product_pagesize_payloads=pagesize_payloads,
        product_spenum_payloads=spenum_payloads,
    )

    output = {
        "captured_at": now_local().isoformat(),
        "endpoint": "SelWareList",
        "source_url": PRODUCT_URL,
        "baseline_payload": BASELINE_PAYLOAD,
        "page_probes": PAGE_PROBES,
        "pagesize_probes": PAGESIZE_PROBES,
        "spenum_probe_keys": list(BROAD_SPENUM_PROBES) + exact_codes,
        **evidence,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({"ok": True, "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
