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
    build_store_stocktaking_capture_research_bundle,
    persist_store_stocktaking_capture_research_bundle,
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


STORE_STOCKTAKING_SOURCE_ENDPOINT = "yeusoft.docs.store_stocktaking_list"
STORE_STOCKTAKING_URL = "https://jyapistaging.yeusoft.net/JyApi/EposDoc/SelDocManageList"


def _latest_store_stocktaking_evidence_path() -> Path:
    analysis_dir = PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"
    candidates = sorted(analysis_dir.glob("store-stocktaking-evidence-chain-*.json"))
    if not candidates:
        raise FileNotFoundError("未找到 store-stocktaking-evidence-chain 分析文件")
    return candidates[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description="把 Yeusoft 门店盘点单按 research-capture 路线写入 capture。")
    parser.add_argument("--readme", default=str(README_PATH))
    parser.add_argument("--transport", choices=["curl", "urllib"], default="curl")
    parser.add_argument("--skip-db", action="store_true", help="只输出 research bundle 摘要，不写 capture")
    parser.add_argument("--capture-batch-id", help="指定 capture_batch_id")
    parser.add_argument(
        "--output",
        help="输出 research JSON；默认写入 tmp/capture-samples/analysis/store-stocktaking-capture-research-<timestamp>.json",
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
        / f"store-stocktaking-capture-research-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    )

    evidence_path = _latest_store_stocktaking_evidence_path()
    stocktaking_evidence = json.loads(evidence_path.read_text("utf-8"))
    detail = dict((stocktaking_evidence.get("store_stocktaking") or {}))
    baseline_request_payload = dict((detail.get("capture_parameter_plan") or {}).get("baseline_payload") or {})
    if not baseline_request_payload:
        raise RuntimeError("门店盘点单 evidence 缺少 baseline_payload，暂不执行 capture research admit")

    auth = read_login_auth(readme)
    access_token, _ = refresh_session_access_token(auth)
    headers = build_report_auth_headers(STORE_STOCKTAKING_URL, access_token)
    status, baseline_payload = perform_request(args.transport, STORE_STOCKTAKING_URL, baseline_request_payload, headers)
    if status != 200:
        raise RuntimeError(f"门店盘点单 baseline 返回 HTTP {status}")

    capture_batch_id = None
    if not args.skip_db:
        init_databases()
        capture_batch_id = create_capture_batch(
            source_name="store-stocktaking-capture-research",
            capture_batch_id=args.capture_batch_id,
        )
        bootstrap_capture_batch(capture_batch_id, auth, auth.company_code or "", auth.api_base_url)
        bundle = persist_store_stocktaking_capture_research_bundle(
            capture_batch_id=capture_batch_id,
            stocktaking_evidence=stocktaking_evidence,
            baseline_payload=baseline_payload,
            baseline_request_payload=baseline_request_payload,
            source_endpoint=STORE_STOCKTAKING_SOURCE_ENDPOINT,
            account_context={
                "company_code": auth.company_code,
                "dept_code": auth.dept_code,
                "dept_name": auth.dept_name,
                "user_name": auth.user_name,
            },
        )
        update_capture_batch(capture_batch_id, batch_status="captured", pulled_at=now_local())
    else:
        bundle = build_store_stocktaking_capture_research_bundle(stocktaking_evidence=stocktaking_evidence)

    output = {
        "captured_at": now_local().isoformat(),
        "capture_batch_id": capture_batch_id,
        "store_stocktaking_evidence_source": str(evidence_path.relative_to(PROJECT_ROOT)),
        "source_endpoint": STORE_STOCKTAKING_SOURCE_ENDPOINT,
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
