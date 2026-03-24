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
    build_store_stocktaking_diff_capture_research_bundle,
    persist_store_stocktaking_diff_capture_research_bundle,
)
from scripts.fetch_yeusoft_report_payloads import README_PATH, bootstrap_capture_batch, now_local, read_login_auth


STORE_STOCKTAKING_DIFF_SOURCE_ENDPOINT = "yeusoft.ui.store_stocktaking_diff_state"


def _latest_store_stocktaking_ui_probe_path() -> Path:
    analysis_dir = PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"
    candidates = sorted(analysis_dir.glob("store-stocktaking-ui-probe-*.json"))
    if not candidates:
        raise FileNotFoundError("未找到 store-stocktaking-ui-probe 分析文件")
    return candidates[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description="把门店盘点单的本地损溢二级数据写入 capture research route。")
    parser.add_argument("--readme", default=str(README_PATH))
    parser.add_argument("--skip-db", action="store_true", help="只输出 research bundle 摘要，不写 capture")
    parser.add_argument("--capture-batch-id", help="指定 capture_batch_id")
    parser.add_argument(
        "--output",
        help="输出 research JSON；默认写入 tmp/capture-samples/analysis/store-stocktaking-diff-capture-research-<timestamp>.json",
    )
    args = parser.parse_args()

    output_path = (
        Path(args.output)
        if args.output
        else PROJECT_ROOT
        / "tmp"
        / "capture-samples"
        / "analysis"
        / f"store-stocktaking-diff-capture-research-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    )

    ui_probe_path = _latest_store_stocktaking_ui_probe_path()
    ui_probe_payload = json.loads(ui_probe_path.read_text("utf-8"))
    auth = read_login_auth(Path(args.readme))

    capture_batch_id = None
    if not args.skip_db:
        init_databases()
        capture_batch_id = create_capture_batch(
            source_name="store-stocktaking-diff-capture-research",
            capture_batch_id=args.capture_batch_id,
        )
        bootstrap_capture_batch(capture_batch_id, auth, auth.company_code or "", auth.api_base_url)
        bundle = persist_store_stocktaking_diff_capture_research_bundle(
            capture_batch_id=capture_batch_id,
            ui_probe_payload=ui_probe_payload,
            source_endpoint=STORE_STOCKTAKING_DIFF_SOURCE_ENDPOINT,
            account_context={
                "company_code": auth.company_code,
                "dept_code": auth.dept_code,
                "dept_name": auth.dept_name,
                "user_name": auth.user_name,
            },
        )
        update_capture_batch(capture_batch_id, batch_status="captured", pulled_at=now_local())
    else:
        bundle = build_store_stocktaking_diff_capture_research_bundle(ui_probe_payload=ui_probe_payload)

    output = {
        "captured_at": now_local().isoformat(),
        "capture_batch_id": capture_batch_id,
        "store_stocktaking_ui_probe_source": str(ui_probe_path.relative_to(PROJECT_ROOT)),
        "source_endpoint": STORE_STOCKTAKING_DIFF_SOURCE_ENDPOINT,
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
