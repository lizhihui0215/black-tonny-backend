#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.erp_research_service import build_sales_menu_grain_analysis
from scripts.fetch_yeusoft_report_payloads import (
    README_PATH,
    REPORT_DOC_PATH,
    find_report_spec_by_title,
    maybe_override_url,
    perform_request,
    read_login_auth,
    refresh_session_access_token,
)

LOCAL_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"
SALES_MENU_ID = "E004001008"
GRID_VIEW_URL = "https://jyapistaging.yeusoft.net/JyApi/Grid/GetViewGridList"
SALES_REPORT_URL = "https://erpapistaging.yeusoft.net/eposapi/YisEposReport/SelSaleReport"
DEFAULT_SALE_REPORT_PAYLOAD = {
    "edate": "20260401",
    "bdate": "20250301",
    "saletype": "0",
    "type": "0",
    "val": "",
    "page": 1,
    "pagesize": 999999,
    "isshow": "1",
}


def now_local() -> datetime:
    return datetime.now(LOCAL_TZ)


def post_with_auth(*, url: str, payload: dict[str, object], api_base_url: str | None, access_token: str) -> tuple[str, dict]:
    final_url = maybe_override_url(type("Spec", (), {"url": url})(), api_base_url)
    headers = {"Authorization": f"Bearer {access_token}"} if "/JyApi/" in final_url else {"token": access_token}
    status, data = perform_request("curl", final_url, payload, headers)
    if status != 200:
        raise RuntimeError(f"{final_url} 返回 HTTP {status}")
    if not isinstance(data, dict):
        raise RuntimeError(f"{final_url} 返回非 JSON object")
    return final_url, data


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取并分析 Yeusoft 销售菜单在按单据/按明细两种粒度下的结构差异。")
    parser.add_argument("--readme", default=str(README_PATH), help="账号说明文件路径")
    parser.add_argument("--report-doc", default=str(REPORT_DOC_PATH), help="report_api_samples.md 路径")
    parser.add_argument("--output", help="输出 JSON 文件路径；默认写入 tmp/capture-samples/analysis")
    args = parser.parse_args()

    report_doc = Path(args.report_doc)
    readme = Path(args.readme)
    output_path = (
        Path(args.output)
        if args.output
        else DEFAULT_OUTPUT_ROOT / f"sales-menu-grain-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    )

    auth = read_login_auth(readme)
    access_token, _ = refresh_session_access_token(auth)
    api_base_url = auth.raw_login_data.get("JyApiUrl") if auth.raw_login_data else auth.api_base_url

    sales_list_spec = find_report_spec_by_title(report_doc, "销售清单")
    if sales_list_spec is None:
        raise RuntimeError("未在 report_api_samples.md 中找到销售清单请求")
    if not isinstance(sales_list_spec.payload, dict):
        raise RuntimeError("销售清单请求 payload 不是 JSON object")

    grid_1_url, grid_1_payload = post_with_auth(
        url=GRID_VIEW_URL,
        payload={"menuid": SALES_MENU_ID, "gridid": f"{SALES_MENU_ID}_1", "isJyApi": True},
        api_base_url=api_base_url,
        access_token=access_token,
    )
    grid_2_url, grid_2_payload = post_with_auth(
        url=GRID_VIEW_URL,
        payload={"menuid": SALES_MENU_ID, "gridid": f"{SALES_MENU_ID}_2", "isJyApi": True},
        api_base_url=api_base_url,
        access_token=access_token,
    )
    sale_report_url, sale_report_payload = post_with_auth(
        url=SALES_REPORT_URL,
        payload=DEFAULT_SALE_REPORT_PAYLOAD,
        api_base_url=api_base_url,
        access_token=access_token,
    )
    sales_list_url, sales_list_payload = post_with_auth(
        url=sales_list_spec.url,
        payload=sales_list_spec.payload,
        api_base_url=api_base_url,
        access_token=access_token,
    )

    analysis = build_sales_menu_grain_analysis(
        menuid=SALES_MENU_ID,
        document_grid_payload=grid_1_payload,
        detail_grid_payload=grid_2_payload,
        document_data_payload=sale_report_payload,
        detail_data_payload=sales_list_payload,
    )

    output = {
        "fetched_at": now_local().isoformat(),
        "auth_context": {
            "company_code": auth.company_code,
            "dept_code": auth.dept_code,
            "dept_name": auth.dept_name,
            "user_name": auth.user_name,
        },
        "requests": {
            "grid_1": {
                "url": grid_1_url,
                "payload": {"menuid": SALES_MENU_ID, "gridid": f"{SALES_MENU_ID}_1", "isJyApi": True},
            },
            "grid_2": {
                "url": grid_2_url,
                "payload": {"menuid": SALES_MENU_ID, "gridid": f"{SALES_MENU_ID}_2", "isJyApi": True},
            },
            "sel_sale_report": {
                "url": sale_report_url,
                "payload": DEFAULT_SALE_REPORT_PAYLOAD,
            },
            "sales_list_detail": {
                "url": sales_list_url,
                "payload": sales_list_spec.payload,
            },
        },
        "analysis": analysis,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({"ok": True, "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
