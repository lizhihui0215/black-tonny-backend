#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.engine import init_databases
from app.services.batch_service import create_capture_batch, update_capture_batch
from app.services.sales_capture_admission_service import persist_sales_capture_admission_bundle
from scripts.analyze_yeusoft_sales_evidence_chain import DEFAULT_SALE_REPORT_PAYLOAD, SALES_REPORT_URL
from scripts.fetch_yeusoft_report_payloads import (
    README_PATH,
    REPORT_DOC_PATH,
    build_report_auth_headers,
    bootstrap_capture_batch,
    find_report_spec_by_title,
    maybe_override_url,
    now_local,
    perform_request,
    read_login_auth,
    refresh_session_access_token,
)


DOCUMENT_SOURCE_ENDPOINT = "yeusoft.report.sales_document_route"


def _make_spec(url: str):
    return type("Spec", (), {"url": url})()


def main() -> int:
    parser = argparse.ArgumentParser(description="把 Yeusoft 销售头/行/逆向三条路线首批准入 capture。")
    parser.add_argument("--readme", default=str(README_PATH))
    parser.add_argument("--report-doc", default=str(REPORT_DOC_PATH))
    parser.add_argument("--transport", choices=["curl", "urllib"], default="curl")
    parser.add_argument("--skip-db", action="store_true", help="只输出 admission 摘要，不写 capture")
    parser.add_argument("--capture-batch-id", help="指定 capture_batch_id")
    parser.add_argument(
        "--output",
        help="输出 admission JSON；默认写入 tmp/capture-samples/analysis/sales-capture-admission-<timestamp>.json",
    )
    args = parser.parse_args()

    readme = Path(args.readme)
    report_doc = Path(args.report_doc)
    output_path = (
        Path(args.output)
        if args.output
        else PROJECT_ROOT
        / "tmp"
        / "capture-samples"
        / "analysis"
        / f"sales-capture-admission-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    )

    auth = read_login_auth(readme)
    access_token, _ = refresh_session_access_token(auth)
    api_base_url = auth.raw_login_data.get("JyApiUrl") if auth.raw_login_data else auth.api_base_url

    sales_list_spec = find_report_spec_by_title(report_doc, "销售清单")
    if sales_list_spec is None or not isinstance(sales_list_spec.payload, dict):
        raise RuntimeError("未在 report_api_samples.md 中找到可用的 销售清单 payload")

    document_url = maybe_override_url(_make_spec(SALES_REPORT_URL), api_base_url)
    detail_url = maybe_override_url(sales_list_spec, api_base_url)
    document_headers = build_report_auth_headers(document_url, access_token)
    detail_headers = build_report_auth_headers(detail_url, access_token)

    document_status, document_payload = perform_request(
        args.transport,
        document_url,
        DEFAULT_SALE_REPORT_PAYLOAD,
        document_headers,
    )
    detail_status, detail_payload = perform_request(
        args.transport,
        detail_url,
        sales_list_spec.payload,
        detail_headers,
    )
    if document_status != 200:
        raise RuntimeError(f"SelSaleReport 返回 HTTP {document_status}")
    if detail_status != 200:
        raise RuntimeError(f"销售清单(_2) 返回 HTTP {detail_status}")

    capture_batch_id = None
    if not args.skip_db:
        init_databases()
        capture_batch_id = create_capture_batch(
            source_name="sales-capture-admission",
            capture_batch_id=args.capture_batch_id,
        )
        bootstrap_capture_batch(capture_batch_id, auth, auth.company_code or "", api_base_url)
        bundle = persist_sales_capture_admission_bundle(
            capture_batch_id=capture_batch_id,
            document_payload=document_payload,
            detail_payload=detail_payload,
            document_request_payload=DEFAULT_SALE_REPORT_PAYLOAD,
            detail_request_payload=sales_list_spec.payload,
            document_source_endpoint=DOCUMENT_SOURCE_ENDPOINT,
            detail_source_endpoint=sales_list_spec.source_endpoint,
            account_context={
                "company_code": auth.company_code,
                "dept_code": auth.dept_code,
                "dept_name": auth.dept_name,
                "user_name": auth.user_name,
            },
        )
        update_capture_batch(capture_batch_id, batch_status="captured", pulled_at=now_local())
    else:
        from app.services.sales_capture_admission_service import build_sales_capture_admission_bundle

        bundle = build_sales_capture_admission_bundle(
            document_payload=document_payload,
            detail_payload=detail_payload,
        )

    output = {
        "captured_at": now_local().isoformat(),
        "capture_batch_id": capture_batch_id,
        "document_source_endpoint": DOCUMENT_SOURCE_ENDPOINT,
        "detail_source_endpoint": sales_list_spec.source_endpoint,
        "document_request_payload": DEFAULT_SALE_REPORT_PAYLOAD,
        "detail_request_payload": sales_list_spec.payload,
        "account_context": {
            "company_code": auth.company_code,
            "dept_code": auth.dept_code,
            "dept_name": auth.dept_name,
            "user_name": auth.user_name,
        },
        "summary": bundle,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({"ok": True, "capture_batch_id": capture_batch_id, "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
