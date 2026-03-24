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
    MEMBER_MAINTENANCE_RECORDS_ENDPOINT,
    build_member_maintenance_capture_research_bundle,
    persist_member_maintenance_capture_research_bundle,
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


MEMBER_MAINTENANCE_SOURCE_ENDPOINT = "yeusoft.member.member_maintenance"
MEMBER_MAINTENANCE_URL = "https://erpapistaging.yeusoft.net/eposapi/YisEposVipReturnVisit/SelVipReturnVisitList"
MEMBER_MAINTENANCE_BASELINE_PAYLOAD = {
    "search": "",
    "brdate": "",
    "erdate": "",
    "bdate": "",
    "edate": "",
    "type": "",
    "page": 1,
    "pagesize": 20,
}


def _latest_member_maintenance_evidence_path() -> Path:
    analysis_dir = PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"
    candidates = sorted(analysis_dir.glob("member-maintenance-evidence-chain-*.json"))
    if not candidates:
        raise FileNotFoundError("未找到 member-maintenance-evidence-chain 分析文件")
    return candidates[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description="把 Yeusoft 会员维护按 research-capture 路线写入 capture。")
    parser.add_argument("--readme", default=str(README_PATH))
    parser.add_argument("--transport", choices=["curl", "urllib"], default="curl")
    parser.add_argument("--skip-db", action="store_true", help="只输出 research bundle 摘要，不写 capture")
    parser.add_argument("--capture-batch-id", help="指定 capture_batch_id")
    parser.add_argument(
        "--output",
        help="输出 research JSON；默认写入 tmp/capture-samples/analysis/member-maintenance-capture-research-<timestamp>.json",
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
        / f"member-maintenance-capture-research-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    )

    evidence_path = _latest_member_maintenance_evidence_path()
    member_maintenance_evidence = json.loads(evidence_path.read_text("utf-8"))

    auth = read_login_auth(readme)
    access_token, _ = refresh_session_access_token(auth)
    headers = build_report_auth_headers(MEMBER_MAINTENANCE_URL, access_token)
    baseline_request_payload = dict(MEMBER_MAINTENANCE_BASELINE_PAYLOAD)
    status, baseline_payload = perform_request(args.transport, MEMBER_MAINTENANCE_URL, baseline_request_payload, headers)
    if status != 200:
        raise RuntimeError(f"会员维护 baseline 返回 HTTP {status}")

    capture_batch_id = None
    if not args.skip_db:
        init_databases()
        capture_batch_id = create_capture_batch(
            source_name="member-maintenance-capture-research",
            capture_batch_id=args.capture_batch_id,
        )
        bootstrap_capture_batch(capture_batch_id, auth, auth.company_code or "", auth.api_base_url)
        bundle = persist_member_maintenance_capture_research_bundle(
            capture_batch_id=capture_batch_id,
            member_maintenance_evidence=member_maintenance_evidence,
            baseline_payload=baseline_payload,
            baseline_request_payload=baseline_request_payload,
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
        bundle = build_member_maintenance_capture_research_bundle(
            member_maintenance_evidence=member_maintenance_evidence
        )

    output = {
        "captured_at": now_local().isoformat(),
        "capture_batch_id": capture_batch_id,
        "member_maintenance_evidence_source": str(evidence_path.relative_to(PROJECT_ROOT)),
        "source_endpoint": MEMBER_MAINTENANCE_SOURCE_ENDPOINT,
        "capture_route_name": MEMBER_MAINTENANCE_RECORDS_ENDPOINT,
        "request_payload": baseline_request_payload,
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
