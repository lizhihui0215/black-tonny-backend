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
    build_stored_value_capture_research_bundle,
    persist_stored_value_capture_research_bundle,
)
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


def _latest_stored_value_evidence_path() -> Path:
    analysis_dir = PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"
    candidates = sorted(analysis_dir.glob("stored-value-evidence-chain-*.json"))
    if not candidates:
        raise FileNotFoundError("未找到 stored-value-evidence-chain 分析文件")
    return candidates[-1]


def _make_spec(url: str):
    return type("Spec", (), {"url": url})()


def main() -> int:
    parser = argparse.ArgumentParser(description="把 Yeusoft 储值卡明细按 research-capture 路线写入 capture。")
    parser.add_argument("--readme", default=str(README_PATH))
    parser.add_argument("--report-doc", default=str(REPORT_DOC_PATH))
    parser.add_argument("--transport", choices=["curl", "urllib"], default="curl")
    parser.add_argument("--skip-db", action="store_true", help="只输出 research bundle 摘要，不写 capture")
    parser.add_argument("--capture-batch-id", help="指定 capture_batch_id")
    parser.add_argument(
        "--output",
        help="输出 research JSON；默认写入 tmp/capture-samples/analysis/stored-value-capture-research-<timestamp>.json",
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
        / f"stored-value-capture-research-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    )

    stored_value_evidence_path = _latest_stored_value_evidence_path()
    stored_value_evidence = json.loads(stored_value_evidence_path.read_text("utf-8"))

    auth = read_login_auth(readme)
    access_token, _ = refresh_session_access_token(auth)
    api_base_url = auth.raw_login_data.get("JyApiUrl") if auth.raw_login_data else auth.api_base_url

    report_spec = find_report_spec_by_title(report_doc, "储值卡明细")
    if report_spec is None or not isinstance(report_spec.payload, dict):
        raise RuntimeError("未在 report_api_samples.md 中找到可用的 储值卡明细 payload")

    url = maybe_override_url(_make_spec(report_spec.url), api_base_url)
    auth_headers = build_report_auth_headers(url, access_token)
    baseline_request_payload = dict(report_spec.payload)
    status, baseline_payload = perform_request(args.transport, url, baseline_request_payload, auth_headers)
    if status != 200:
        raise RuntimeError(f"储值卡明细 baseline 返回 HTTP {status}")

    capture_batch_id = None
    if not args.skip_db:
        init_databases()
        capture_batch_id = create_capture_batch(
            source_name="stored-value-capture-research",
            capture_batch_id=args.capture_batch_id,
        )
        bootstrap_capture_batch(capture_batch_id, auth, auth.company_code or "", api_base_url)
        bundle = persist_stored_value_capture_research_bundle(
            capture_batch_id=capture_batch_id,
            stored_value_evidence=stored_value_evidence,
            baseline_payload=baseline_payload,
            baseline_request_payload=baseline_request_payload,
            source_endpoint=report_spec.source_endpoint,
            account_context={
                "company_code": auth.company_code,
                "dept_code": auth.dept_code,
                "dept_name": auth.dept_name,
                "user_name": auth.user_name,
            },
        )
        update_capture_batch(capture_batch_id, batch_status="captured", pulled_at=now_local())
    else:
        bundle = build_stored_value_capture_research_bundle(stored_value_evidence=stored_value_evidence)

    output = {
        "captured_at": now_local().isoformat(),
        "capture_batch_id": capture_batch_id,
        "stored_value_evidence_source": str(stored_value_evidence_path.relative_to(PROJECT_ROOT)),
        "source_endpoint": report_spec.source_endpoint,
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
