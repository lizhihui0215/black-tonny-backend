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
    build_customer_capture_admission_bundle,
    persist_customer_capture_admission_bundle,
)
from scripts.fetch_yeusoft_report_payloads import (
    README_PATH,
    build_report_auth_headers,
    bootstrap_capture_batch,
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


def _latest_customer_evidence_path() -> Path:
    analysis_dir = PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"
    candidates = sorted(analysis_dir.glob("customer-evidence-chain-*.json"))
    if not candidates:
        raise FileNotFoundError("未找到 customer-evidence-chain 分析文件")
    return candidates[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description="把 Yeusoft 客户资料按正式主链候选路线准入 capture。")
    parser.add_argument("--readme", default=str(README_PATH))
    parser.add_argument("--transport", choices=["curl", "urllib"], default="curl")
    parser.add_argument("--skip-db", action="store_true", help="只输出 admission 摘要，不写 capture")
    parser.add_argument("--capture-batch-id", help="指定 capture_batch_id")
    parser.add_argument(
        "--output",
        help="输出 admission JSON；默认写入 tmp/capture-samples/analysis/customer-capture-admission-<timestamp>.json",
    )
    args = parser.parse_args()

    output_path = (
        Path(args.output)
        if args.output
        else PROJECT_ROOT
        / "tmp"
        / "capture-samples"
        / "analysis"
        / f"customer-capture-admission-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    )

    customer_evidence_path = _latest_customer_evidence_path()
    customer_evidence = json.loads(customer_evidence_path.read_text("utf-8"))
    customer_list = dict((customer_evidence.get("customer_list") or {}))
    if not bool(customer_list.get("capture_admission_ready")):
        raise RuntimeError("客户资料当前尚未满足 capture admit 条件，请先刷新 customer evidence")

    auth = read_login_auth(Path(args.readme))
    access_token, _ = refresh_session_access_token(auth)
    headers = build_report_auth_headers(CUSTOMER_URL, access_token)
    request_payload = dict(CUSTOMER_BASELINE_PAYLOAD)
    status, baseline_payload = perform_request(args.transport, CUSTOMER_URL, request_payload, headers)
    if status != 200:
        raise RuntimeError(f"客户资料 baseline 返回 HTTP {status}")

    capture_batch_id = None
    if not args.skip_db:
        init_databases()
        capture_batch_id = create_capture_batch(
            source_name="customer-capture-admission",
            capture_batch_id=args.capture_batch_id,
        )
        bootstrap_capture_batch(capture_batch_id, auth, auth.company_code or "", auth.api_base_url)
        bundle = persist_customer_capture_admission_bundle(
            capture_batch_id=capture_batch_id,
            customer_evidence=customer_evidence,
            baseline_payload=baseline_payload,
            baseline_request_payload=request_payload,
            source_endpoint=CUSTOMER_SOURCE_ENDPOINT,
            account_context={
                "company_code": auth.company_code,
                "dept_code": auth.dept_code,
                "dept_name": auth.dept_name,
                "user_name": auth.user_name,
            },
        )
        update_capture_batch(capture_batch_id, batch_status="captured", pulled_at=now_local())
    else:
        bundle = build_customer_capture_admission_bundle(
            customer_evidence=customer_evidence,
            baseline_payload=baseline_payload,
            baseline_request_payload=request_payload,
        )

    output = {
        "captured_at": now_local().isoformat(),
        "capture_batch_id": capture_batch_id,
        "customer_evidence_source": str(customer_evidence_path.relative_to(PROJECT_ROOT)),
        "source_endpoint": CUSTOMER_SOURCE_ENDPOINT,
        "request_payload": request_payload,
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
