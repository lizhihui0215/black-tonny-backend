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
from app.services.product_capture_admission_service import persist_product_capture_admission_bundle
from app.services.product_evidence_service import extract_declared_total_count
from scripts.fetch_yeusoft_report_payloads import (
    README_PATH,
    build_report_auth_headers,
    bootstrap_capture_batch,
    now_local,
    perform_request,
    read_login_auth,
    refresh_session_access_token,
)


PRODUCT_SOURCE_ENDPOINT = "yeusoft.master.product_list"
PRODUCT_URL = "https://erpapistaging.yeusoft.net/eposapi/YisEposWareList/SelWareList"


def _latest_product_evidence_path() -> Path:
    analysis_dir = PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"
    candidates = sorted(analysis_dir.glob("product-evidence-chain-*.json"))
    if not candidates:
        raise FileNotFoundError("未找到 product-evidence-chain 分析文件")
    return candidates[-1]


def _extract_rows(payload: dict[str, object] | list[object]) -> list[object]:
    if not isinstance(payload, dict):
        return []
    retdata = payload.get("retdata")
    if isinstance(retdata, list) and retdata and isinstance(retdata[0], dict):
        rows = retdata[0].get("Data")
        if isinstance(rows, list):
            return rows
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="把 Yeusoft 商品资料按正式主链候选路线准入 capture。")
    parser.add_argument("--readme", default=str(README_PATH))
    parser.add_argument("--transport", choices=["curl", "urllib"], default="curl")
    parser.add_argument("--skip-db", action="store_true", help="只输出 admission 摘要，不写 capture")
    parser.add_argument("--capture-batch-id", help="指定 capture_batch_id")
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument(
        "--output",
        help="输出 admission JSON；默认写入 tmp/capture-samples/analysis/product-capture-admission-<timestamp>.json",
    )
    args = parser.parse_args()

    output_path = (
        Path(args.output)
        if args.output
        else PROJECT_ROOT
        / "tmp"
        / "capture-samples"
        / "analysis"
        / f"product-capture-admission-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    )

    product_evidence_path = _latest_product_evidence_path()
    product_evidence = json.loads(product_evidence_path.read_text("utf-8"))
    product_list = dict((product_evidence.get("product_list") or {}))
    if not bool(product_list.get("capture_admission_ready")):
        raise RuntimeError("商品资料当前尚未满足 capture admit 条件，请先刷新 product evidence")

    capture_plan = dict((product_list.get("capture_parameter_plan") or {}))
    recommended_pagesize = int(capture_plan.get("recommended_pagesize") or 5000)
    baseline_page = int(capture_plan.get("baseline_page") or 1)

    auth = read_login_auth(Path(args.readme))
    access_token, _ = refresh_session_access_token(auth)
    headers = build_report_auth_headers(PRODUCT_URL, access_token)

    page_payloads: dict[int, dict[str, object] | list[object]] = {}
    page_request_payloads: dict[int, dict[str, object]] = {}
    observed_total_rows = 0
    declared_total_count = None

    for page_no in range(baseline_page, baseline_page + args.max_pages):
        request_payload = {
            "spenum": capture_plan.get("default_spenum", ""),
            "warecause": capture_plan.get("default_warecause", ""),
            "page": page_no,
            "pagesize": recommended_pagesize,
        }
        status, payload = perform_request(args.transport, PRODUCT_URL, request_payload, headers)
        if status != 200:
            raise RuntimeError(f"商品资料 page={page_no} 返回 HTTP {status}")
        page_payloads[page_no] = payload
        page_request_payloads[page_no] = copy.deepcopy(request_payload)
        rows = _extract_rows(payload)
        row_count = len(rows)
        observed_total_rows += row_count
        declared_total_count = declared_total_count or extract_declared_total_count(payload)
        if row_count == 0:
            break
        if declared_total_count is not None and observed_total_rows >= declared_total_count:
            break
        if row_count < recommended_pagesize:
            break

    capture_batch_id = None
    if not args.skip_db:
        init_databases()
        capture_batch_id = create_capture_batch(
            source_name="product-capture-admission",
            capture_batch_id=args.capture_batch_id,
        )
        bootstrap_capture_batch(capture_batch_id, auth, auth.company_code or "", auth.api_base_url)
        bundle = persist_product_capture_admission_bundle(
            capture_batch_id=capture_batch_id,
            product_evidence=product_evidence,
            page_payloads=page_payloads,
            page_request_payloads=page_request_payloads,
            source_endpoint=PRODUCT_SOURCE_ENDPOINT,
            account_context={
                "company_code": auth.company_code,
                "dept_code": auth.dept_code,
                "dept_name": auth.dept_name,
                "user_name": auth.user_name,
            },
        )
        update_capture_batch(capture_batch_id, batch_status="captured", pulled_at=now_local())
    else:
        from app.services.product_capture_admission_service import build_product_capture_admission_bundle

        bundle = build_product_capture_admission_bundle(
            product_evidence=product_evidence,
            page_payloads=page_payloads,
            page_request_payloads=page_request_payloads,
        )

    output = {
        "captured_at": now_local().isoformat(),
        "capture_batch_id": capture_batch_id,
        "product_evidence_source": str(product_evidence_path.relative_to(PROJECT_ROOT)),
        "source_endpoint": PRODUCT_SOURCE_ENDPOINT,
        "request_payloads": page_request_payloads,
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
