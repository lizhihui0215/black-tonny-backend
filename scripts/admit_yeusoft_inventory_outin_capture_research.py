#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.engine import init_databases
from app.services.batch_service import create_capture_batch, update_capture_batch
from app.services.inventory_capture_admission_service import (
    build_outin_research_sweep_summary,
    build_inventory_capture_admission_bundle,
    persist_outin_capture_research_bundle,
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


def _latest_inventory_evidence_path() -> Path:
    analysis_dir = PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"
    candidates = sorted(analysis_dir.glob("inventory-evidence-chain-*.json"))
    if not candidates:
        raise FileNotFoundError("未找到 inventory-evidence-chain 分析文件")
    return candidates[-1]


def _make_spec(url: str):
    return type("Spec", (), {"url": url})()


def main() -> int:
    parser = argparse.ArgumentParser(description="把 Yeusoft 出入库单据最小 sweep 组合写入 capture research 层。")
    parser.add_argument("--readme", default=str(README_PATH))
    parser.add_argument("--report-doc", default=str(REPORT_DOC_PATH))
    parser.add_argument("--transport", choices=["curl", "urllib"], default="curl")
    parser.add_argument("--skip-db", action="store_true", help="只输出 research 摘要，不写 capture")
    parser.add_argument("--capture-batch-id", help="指定 capture_batch_id")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="限制 sweep 组合数，0 表示使用全部 recommended_minimum_sweeps",
    )
    parser.add_argument(
        "--output",
        help="输出 JSON；默认写入 tmp/capture-samples/analysis/inventory-outin-capture-research-<timestamp>.json",
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
        / f"inventory-outin-capture-research-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    )

    inventory_evidence_path = _latest_inventory_evidence_path()
    inventory_evidence = json.loads(inventory_evidence_path.read_text("utf-8"))
    admission_bundle = build_inventory_capture_admission_bundle(inventory_evidence=inventory_evidence)
    outin_bundle = admission_bundle["outin_report"]
    expected_sweeps = list(outin_bundle.get("recommended_minimum_sweeps") or [])
    if args.limit and args.limit > 0:
        expected_sweeps = expected_sweeps[: args.limit]

    auth = read_login_auth(readme)
    access_token, _ = refresh_session_access_token(auth)
    api_base_url = auth.raw_login_data.get("JyApiUrl") if auth.raw_login_data else auth.api_base_url

    report_spec = find_report_spec_by_title(report_doc, "出入库单据")
    if report_spec is None or not isinstance(report_spec.payload, dict):
        raise RuntimeError("未在 report_api_samples.md 中找到可用的 出入库单据 payload")

    url = maybe_override_url(_make_spec(report_spec.url), api_base_url)
    headers = build_report_auth_headers(url, access_token)
    sweep_payloads: list[dict[str, object]] = []
    for combo in expected_sweeps:
        request_payload = copy.deepcopy(report_spec.payload)
        request_payload["datetype"] = combo["datetype"]
        request_payload["type"] = combo["type"]
        request_payload["doctype"] = combo["doctype"]
        status, payload = perform_request(args.transport, url, request_payload, headers)
        if status != 200:
            raise RuntimeError(
                f"出入库单据组合 {combo['key']} 返回 HTTP {status}"
            )
        sweep_payloads.append(
            {
                "datetype": combo["datetype"],
                "type": combo["type"],
                "doctype": combo["doctype"],
                "payload": payload,
                "request_payload": request_payload,
            }
        )

    capture_batch_id = None
    if not args.skip_db:
        init_databases()
        capture_batch_id = create_capture_batch(
            source_name="inventory-outin-capture-research",
            capture_batch_id=args.capture_batch_id,
        )
        bootstrap_capture_batch(capture_batch_id, auth, auth.company_code or "", api_base_url)
        result_bundle = persist_outin_capture_research_bundle(
            capture_batch_id=capture_batch_id,
            inventory_evidence=inventory_evidence,
            sweep_payloads=sweep_payloads,
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
        sweep_summary = build_outin_research_sweep_summary(
            expected_sweeps=expected_sweeps,
            sweep_payloads=sweep_payloads,
        )
        result_bundle = build_inventory_capture_admission_bundle(
            inventory_evidence=inventory_evidence,
            outin_research_sweep_summary=sweep_summary,
        )

    output = {
        "captured_at": now_local().isoformat(),
        "capture_batch_id": capture_batch_id,
        "inventory_evidence_source": str(inventory_evidence_path.relative_to(PROJECT_ROOT)),
        "source_endpoint": report_spec.source_endpoint,
        "requested_sweep_count": len(expected_sweeps),
        "request_combos": expected_sweeps,
        "account_context": {
            "company_code": auth.company_code,
            "dept_code": auth.dept_code,
            "dept_name": auth.dept_name,
            "user_name": auth.user_name,
        },
        "summary": result_bundle,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({"ok": True, "capture_batch_id": capture_batch_id, "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
