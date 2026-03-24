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
from app.services.capture.admissions import persist_return_detail_capture_research_bundle
from app.services.capture.batch_lifecycle import create_capture_batch, update_capture_batch
from app.services.capture.route_registry import build_capture_route_registry_from_board
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


RETURN_DETAIL_SOURCE_ENDPOINT = "yeusoft.docs.return_detail"
RETURN_DETAIL_URL = "https://erpapistaging.yeusoft.net/eposapi/YisEposReport/SelReturnStockList"


def _load_latest_json(glob_pattern: str) -> tuple[Path, dict[str, object]]:
    analysis_root = PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"
    matches = sorted(analysis_root.glob(glob_pattern))
    if not matches:
        raise RuntimeError(f"未找到分析产物: {glob_pattern}")
    path = matches[-1]
    payload = json.loads(path.read_text("utf-8"))
    return path, payload


def main() -> int:
    parser = argparse.ArgumentParser(description="把 Yeusoft 退货明细按 research-capture 路线写入 capture。")
    parser.add_argument("--readme", default=str(README_PATH))
    parser.add_argument("--transport", choices=["curl", "urllib"], default="curl")
    parser.add_argument("--skip-db", action="store_true", help="只输出 research bundle 摘要，不写 capture")
    parser.add_argument("--capture-batch-id", help="指定 capture_batch_id")
    parser.add_argument(
        "--output",
        help="输出 research JSON；默认写入 tmp/capture-samples/analysis/return-detail-capture-research-<timestamp>.json",
    )
    args = parser.parse_args()

    output_path = (
        Path(args.output)
        if args.output
        else PROJECT_ROOT
        / "tmp"
        / "capture-samples"
        / "analysis"
        / f"return-detail-capture-research-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    )

    evidence_path, return_detail_evidence = _load_latest_json("return-detail-evidence-chain-*.json")
    ui_probe_path, ui_probe_payload = _load_latest_json("return-detail-ui-probe-*.json")

    board = build_api_maturity_board(PROJECT_ROOT, PROJECT_ROOT / "tmp" / "capture-samples" / "analysis")
    registry = build_capture_route_registry_from_board(board)
    route = next((item for item in registry["routes"] if item["route"] == "退货明细 / SelReturnStockList"), None)
    if route is None:
        raise RuntimeError("当前 capture route registry 里找不到 退货明细 / SelReturnStockList")

    readme = Path(args.readme)
    auth = read_login_auth(readme)
    access_token, _ = refresh_session_access_token(auth)
    headers = build_report_auth_headers(RETURN_DETAIL_URL, access_token)
    baseline_request_payload = dict(
        (((return_detail_evidence.get("return_detail") or {}).get("capture_parameter_plan") or {}).get("baseline_payload") or {})
    )
    status, baseline_payload = perform_request(args.transport, RETURN_DETAIL_URL, baseline_request_payload, headers)
    if status != 200:
        raise RuntimeError(f"退货明细 baseline 返回 HTTP {status}")

    capture_batch_id = None
    if not args.skip_db:
        init_databases()
        capture_batch_id = create_capture_batch(
            source_name="return-detail-capture-research",
            capture_batch_id=args.capture_batch_id,
        )
        bootstrap_capture_batch(capture_batch_id, auth, auth.company_code or "", auth.api_base_url)
        bundle = persist_return_detail_capture_research_bundle(
            capture_batch_id=capture_batch_id,
            return_detail_evidence=return_detail_evidence,
            baseline_payload=baseline_payload,
            baseline_request_payload=baseline_request_payload,
            source_endpoint=RETURN_DETAIL_SOURCE_ENDPOINT,
            account_context={
                "company_code": auth.company_code,
                "dept_code": auth.dept_code,
                "dept_name": auth.dept_name,
                "user_name": auth.user_name,
            },
            ui_probe_payload={**ui_probe_payload, "_analysis_output": str(ui_probe_path)},
        )
        update_capture_batch(capture_batch_id, batch_status="captured", pulled_at=now_local())
    else:
        from app.services.return_detail_capture_admission_service import build_return_detail_capture_research_bundle

        bundle = build_return_detail_capture_research_bundle(
            return_detail_evidence=return_detail_evidence,
            ui_probe_payload={**ui_probe_payload, "_analysis_output": str(ui_probe_path)},
        )

    output = {
        "captured_at": now_local().isoformat(),
        "capture_batch_id": capture_batch_id,
        "source_endpoint": RETURN_DETAIL_SOURCE_ENDPOINT,
        "request_payload": baseline_request_payload,
        "analysis_sources": [str(evidence_path), str(ui_probe_path)],
        "account_context": {
            "company_code": auth.company_code,
            "dept_code": auth.dept_code,
            "dept_name": auth.dept_name,
            "user_name": auth.user_name,
        },
        "summary": bundle,
        "registry_status": {
            "capture_status": route["capture_status"],
            "planned_capture_wave": route["planned_capture_wave"],
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({"ok": True, "capture_batch_id": capture_batch_id, "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
