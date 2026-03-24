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
from app.services.capture.batch_lifecycle import create_capture_batch, update_capture_batch
from app.services.capture.admissions import (
    build_customer_capture_research_bundle,
    persist_customer_capture_research_bundle,
)
from app.services.erp_research_service import analyze_response_payload
from app.services.research.maturity_board import build_api_maturity_board
from scripts.fetch_yeusoft_report_payloads import (
    README_PATH,
    bootstrap_capture_batch,
    build_report_auth_headers,
    now_local,
    perform_request,
    read_login_auth,
    refresh_session_access_token,
)


CUSTOMER_SOURCE_ENDPOINT = "yeusoft.master.customer_list"
CUSTOMER_URL = "https://erpapistaging.yeusoft.net/eposapi/YisEposDeptClientSet/SelDeptList"
CUSTOMER_BASELINE_PAYLOAD = {
    "deptname": "",
    "page": 1,
    "pagesize": 20,
}


def _load_customer_board_entry() -> dict[str, object]:
    analysis_root = PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"
    board = build_api_maturity_board(PROJECT_ROOT, analysis_root)
    for entry in board["entries"]:
        if str(entry.get("title") or "") == "客户资料":
            return dict(entry)
    raise RuntimeError("当前状态板里找不到 客户资料 路线")


def main() -> int:
    parser = argparse.ArgumentParser(description="把 Yeusoft 客户资料按 research-capture 路线写入 capture。")
    parser.add_argument("--readme", default=str(README_PATH))
    parser.add_argument("--transport", choices=["curl", "urllib"], default="curl")
    parser.add_argument("--skip-db", action="store_true", help="只输出 research bundle 摘要，不写 capture")
    parser.add_argument("--capture-batch-id", help="指定 capture_batch_id")
    parser.add_argument(
        "--output",
        help="输出 research JSON；默认写入 tmp/capture-samples/analysis/customer-capture-research-<timestamp>.json",
    )
    args = parser.parse_args()

    readme = Path(args.readme)
    output_path = (
        Path(args.output)
        if args.output
        else PROJECT_ROOT
        / "tmp"
        / "capture-samples"
        / "analysis"
        / f"customer-capture-research-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    )

    customer_entry = _load_customer_board_entry()
    endpoint = str(customer_entry.get("endpoint") or "")
    if not endpoint.endswith("SelDeptList"):
        raise RuntimeError("客户资料 当前还没有稳定识别到 SelDeptList，暂不执行 capture research admit")

    auth = read_login_auth(readme)
    access_token, _ = refresh_session_access_token(auth)
    baseline_request_payload = dict(CUSTOMER_BASELINE_PAYLOAD)
    headers = build_report_auth_headers(CUSTOMER_URL, access_token)
    status, baseline_payload = perform_request(args.transport, CUSTOMER_URL, baseline_request_payload, headers)
    if status != 200:
        raise RuntimeError(f"客户资料 baseline 返回 HTTP {status}")

    analysis = analyze_response_payload(baseline_payload)
    baseline_row_count = int(analysis.get("row_count") or 0)
    capture_batch_id = None
    blocking_issues = list(customer_entry.get("blocking_issues") or [])
    if baseline_row_count == 0 and "当前账号下 baseline 为空，需确认是否长期为空" not in blocking_issues:
        blocking_issues.append("当前账号下 baseline 为空，需确认是否长期为空")
    page_record = {
        "payload_hints": {
            "pagination_fields": ["page", "pagesize"],
            "search_fields": ["deptname"],
        },
        "endpoint_summaries": [{"endpoint": "SelDeptList", "max_row_count": baseline_row_count}],
    }

    if not args.skip_db:
        init_databases()
        capture_batch_id = create_capture_batch(
            source_name="customer-capture-research",
            capture_batch_id=args.capture_batch_id,
        )
        bootstrap_capture_batch(capture_batch_id, auth, auth.company_code or "", auth.api_base_url)
        bundle = persist_customer_capture_research_bundle(
            capture_batch_id=capture_batch_id,
            customer_page_record=page_record,
            blocking_issues=blocking_issues,
            baseline_payload=baseline_payload,
            baseline_request_payload=baseline_request_payload,
            source_endpoint=CUSTOMER_SOURCE_ENDPOINT,
            account_context={
                "company_code": auth.company_code,
                "dept_code": auth.dept_code,
                "dept_name": auth.dept_name,
                "user_name": auth.user_name,
            },
            baseline_row_count=baseline_row_count,
        )
        update_capture_batch(capture_batch_id, batch_status="captured", pulled_at=now_local())
    else:
        bundle = build_customer_capture_research_bundle(
            customer_page_record=page_record,
            blocking_issues=blocking_issues,
            baseline_row_count=baseline_row_count,
        )

    output = {
        "captured_at": now_local().isoformat(),
        "capture_batch_id": capture_batch_id,
        "source_endpoint": CUSTOMER_SOURCE_ENDPOINT,
        "request_payload": baseline_request_payload,
        "account_context": {
            "company_code": auth.company_code,
            "dept_code": auth.dept_code,
            "dept_name": auth.dept_name,
            "user_name": auth.user_name,
        },
        "baseline_analysis": analysis,
        "summary": bundle,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({"ok": True, "capture_batch_id": capture_batch_id, "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
