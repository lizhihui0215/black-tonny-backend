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
    build_member_maintenance_capture_admission_bundle,
    persist_member_maintenance_capture_admission_bundle,
)
from scripts.admit_yeusoft_member_maintenance_capture_research import (
    MEMBER_MAINTENANCE_BASELINE_PAYLOAD,
    MEMBER_MAINTENANCE_SOURCE_ENDPOINT,
    MEMBER_MAINTENANCE_URL,
    _latest_member_maintenance_evidence_path,
)
from scripts.fetch_yeusoft_report_payloads import (
    README_PATH,
    bootstrap_capture_batch,
    build_report_auth_headers,
    now_local,
    perform_request,
    read_login_auth,
    refresh_session_access_token,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="把 Yeusoft 会员维护按正式主链候选路线准入 capture。")
    parser.add_argument("--readme", default=str(README_PATH))
    parser.add_argument("--transport", choices=["curl", "urllib"], default="curl")
    parser.add_argument("--skip-db", action="store_true", help="只输出 admission 摘要，不写 capture")
    parser.add_argument("--capture-batch-id", help="指定 capture_batch_id")
    parser.add_argument(
        "--output",
        help="输出 admission JSON；默认写入 tmp/capture-samples/analysis/member-maintenance-capture-admission-<timestamp>.json",
    )
    args = parser.parse_args()

    output_path = (
        Path(args.output)
        if args.output
        else PROJECT_ROOT
        / "tmp"
        / "capture-samples"
        / "analysis"
        / f"member-maintenance-capture-admission-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    )

    evidence_path = _latest_member_maintenance_evidence_path()
    member_maintenance_evidence = json.loads(evidence_path.read_text("utf-8"))
    detail = dict((member_maintenance_evidence.get("member_maintenance") or {}))
    if not bool(detail.get("capture_admission_ready")):
        raise RuntimeError("会员维护当前尚未满足 capture admit 条件，请先刷新 member-maintenance evidence")

    auth = read_login_auth(Path(args.readme))
    access_token, _ = refresh_session_access_token(auth)
    headers = build_report_auth_headers(MEMBER_MAINTENANCE_URL, access_token)
    request_payload = dict(MEMBER_MAINTENANCE_BASELINE_PAYLOAD)
    status, baseline_payload = perform_request(args.transport, MEMBER_MAINTENANCE_URL, request_payload, headers)
    if status != 200:
        raise RuntimeError(f"会员维护 baseline 返回 HTTP {status}")

    capture_batch_id = None
    if not args.skip_db:
        init_databases()
        capture_batch_id = create_capture_batch(
            source_name="member-maintenance-capture-admission",
            capture_batch_id=args.capture_batch_id,
        )
        bootstrap_capture_batch(capture_batch_id, auth, auth.company_code or "", auth.api_base_url)
        bundle = persist_member_maintenance_capture_admission_bundle(
            capture_batch_id=capture_batch_id,
            member_maintenance_evidence=member_maintenance_evidence,
            baseline_payload=baseline_payload,
            baseline_request_payload=request_payload,
            source_endpoint=MEMBER_MAINTENANCE_SOURCE_ENDPOINT,
            account_context={
                "company_code": auth.company_code,
                "dept_code": auth.dept_code,
                "dept_name": auth.dept_name,
                "user_name": auth.user_name,
            },
        )
        update_capture_batch(capture_batch_id, batch_status="captured", pulled_at=now_local())
    else:
        bundle = build_member_maintenance_capture_admission_bundle(
            member_maintenance_evidence=member_maintenance_evidence,
            baseline_payload=baseline_payload,
            baseline_request_payload=request_payload,
        )

    output = {
        "captured_at": now_local().isoformat(),
        "capture_batch_id": capture_batch_id,
        "member_maintenance_evidence_source": str(evidence_path.relative_to(PROJECT_ROOT)),
        "source_endpoint": MEMBER_MAINTENANCE_SOURCE_ENDPOINT,
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
