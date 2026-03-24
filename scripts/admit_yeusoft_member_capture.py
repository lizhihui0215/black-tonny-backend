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
    build_member_capture_admission_bundle,
    persist_member_capture_admission_bundle,
)
from scripts.fetch_yeusoft_report_payloads import (
    README_PATH,
    REPORT_DOC_PATH,
    build_report_auth_headers,
    bootstrap_capture_batch,
    curl_post_json,
    find_report_spec_by_title,
    maybe_override_url,
    now_local,
    read_login_auth,
    refresh_session_access_token,
)


MEMBER_SOURCE_ENDPOINT = "yeusoft.report.vip_center"


def _latest_member_evidence_path() -> Path:
    analysis_dir = PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"
    candidates = sorted(analysis_dir.glob("member-evidence-chain-*.json"))
    if not candidates:
        raise FileNotFoundError("未找到 member-evidence-chain 分析文件")
    return candidates[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description="把 Yeusoft 会员中心按正式主链候选路线准入 capture。")
    parser.add_argument("--readme", default=str(README_PATH))
    parser.add_argument("--skip-db", action="store_true", help="只输出 admission 摘要，不写 capture")
    parser.add_argument("--capture-batch-id", help="指定 capture_batch_id")
    parser.add_argument(
        "--output",
        help="输出 admission JSON；默认写入 tmp/capture-samples/analysis/member-capture-admission-<timestamp>.json",
    )
    args = parser.parse_args()

    output_path = (
        Path(args.output)
        if args.output
        else PROJECT_ROOT
        / "tmp"
        / "capture-samples"
        / "analysis"
        / f"member-capture-admission-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    )

    member_evidence_path = _latest_member_evidence_path()
    member_evidence = json.loads(member_evidence_path.read_text("utf-8"))
    member_center = dict((member_evidence.get("member_center") or {}))
    if not bool(member_center.get("capture_admission_ready")):
        raise RuntimeError("会员中心当前尚未满足 capture admit 条件，请先刷新 member evidence")

    auth = read_login_auth(Path(args.readme))
    access_token, _ = refresh_session_access_token(auth)
    spec = find_report_spec_by_title(REPORT_DOC_PATH, "会员中心")
    if spec is None:
        raise RuntimeError("未能在 report_api_samples.md 中找到“会员中心”样本")
    url = maybe_override_url(spec, auth.api_base_url)
    headers = build_report_auth_headers(url, access_token)
    request_payload = dict(spec.payload)
    status, baseline_payload = curl_post_json(url, request_payload, headers)
    if status != 200:
        raise RuntimeError(f"会员中心 baseline 返回 HTTP {status}")

    capture_batch_id = None
    if not args.skip_db:
        init_databases()
        capture_batch_id = create_capture_batch(
            source_name="member-capture-admission",
            capture_batch_id=args.capture_batch_id,
        )
        bootstrap_capture_batch(capture_batch_id, auth, auth.company_code or "", auth.api_base_url)
        bundle = persist_member_capture_admission_bundle(
            capture_batch_id=capture_batch_id,
            member_evidence=member_evidence,
            baseline_payload=baseline_payload,
            baseline_request_payload=request_payload,
            source_endpoint=MEMBER_SOURCE_ENDPOINT,
            account_context={
                "company_code": auth.company_code,
                "dept_code": auth.dept_code,
                "dept_name": auth.dept_name,
                "user_name": auth.user_name,
            },
        )
        update_capture_batch(capture_batch_id, batch_status="captured", pulled_at=now_local())
    else:
        bundle = build_member_capture_admission_bundle(
            member_evidence=member_evidence,
            baseline_payload=baseline_payload,
            baseline_request_payload=request_payload,
        )

    output = {
        "captured_at": now_local().isoformat(),
        "capture_batch_id": capture_batch_id,
        "member_evidence_source": str(member_evidence_path.relative_to(PROJECT_ROOT)),
        "source_endpoint": MEMBER_SOURCE_ENDPOINT,
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
