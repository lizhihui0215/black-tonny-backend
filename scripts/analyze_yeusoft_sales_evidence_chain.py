#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.erp_research_service import (  # noqa: E402
    analyze_response_payload,
    build_sales_head_line_join_analysis,
    build_sales_menu_grain_analysis,
    classify_http_probe_semantics,
    set_nested_payload_value,
)
from app.services.retail_detail_stats_service import (  # noqa: E402
    build_retail_detail_page_payload,
    build_sales_reconciliation_report,
    fetch_retail_detail_pages,
    serialize_retail_detail_pagination_result,
)
from scripts.fetch_yeusoft_report_payloads import (  # noqa: E402
    README_PATH,
    REPORT_DOC_PATH,
    REPORT_DOC_PATH as DEFAULT_REPORT_DOC_PATH,
    build_report_auth_headers,
    find_report_spec_by_title,
    maybe_override_url,
    perform_request,
    read_login_auth,
    refresh_session_access_token,
)

LOCAL_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"
DEFAULT_PAGE_RESEARCH_GLOB = "yeusoft-page-research-*.json"
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


def _make_spec(url: str):
    return type("Spec", (), {"url": url})()


def post_with_auth(
    *,
    url: str,
    payload: dict[str, Any],
    api_base_url: str | None,
    access_token: str,
    transport: str = "curl",
) -> tuple[str, dict[str, Any] | list[Any], dict[str, Any]]:
    final_url = maybe_override_url(_make_spec(url), api_base_url)
    headers = build_report_auth_headers(final_url, access_token)
    status, data = perform_request(transport, final_url, payload, headers)
    if status != 200:
        raise RuntimeError(f"{final_url} 返回 HTTP {status}")
    return final_url, data, analyze_response_payload(data)


def find_latest_page_research_summary(
    path: Path | None = None,
    *,
    required_titles: tuple[str, ...] = (),
) -> tuple[Path, dict[str, Any]]:
    if path is not None:
        payload = json.loads(path.read_text("utf-8"))
        return path, payload

    candidates = sorted(DEFAULT_OUTPUT_ROOT.glob(DEFAULT_PAGE_RESEARCH_GLOB))
    if not candidates:
        raise FileNotFoundError("未找到 Yeusoft 页面研究汇总文件")

    for candidate in reversed(candidates):
        payload = json.loads(candidate.read_text("utf-8"))
        if not required_titles:
            return candidate, payload
        page_titles = {str(page.get("title") or "") for page in payload.get("pages", [])}
        if all(title in page_titles for title in required_titles):
            return candidate, payload

    latest = candidates[-1]
    return latest, json.loads(latest.read_text("utf-8"))


def get_page_summary(analysis_payload: dict[str, Any], title: str) -> dict[str, Any]:
    for page in analysis_payload.get("pages", []):
        if page.get("title") == title:
            return page.get("summary") or page
    raise KeyError(f"页面研究汇总里未找到 {title}")


def build_variant_payload(base_payload: dict[str, Any], path: str, value: Any) -> dict[str, Any]:
    payload = copy.deepcopy(base_payload)
    set_nested_payload_value(payload, path, value)
    return payload


def compare_page_research_to_http(
    *,
    name: str,
    page_research_value: Any,
    http_value: Any,
) -> dict[str, Any]:
    if page_research_value == http_value:
        status = "consistent"
    elif page_research_value in (None, "", "insufficient_evidence"):
        status = "page_research_insufficient_http_confirmed"
    else:
        status = "inconsistent_pending_explanation"
    return {
        "name": name,
        "page_research_value": page_research_value,
        "http_value": http_value,
        "status": status,
    }


def build_issue_flags(
    *,
    join_analysis: dict[str, Any],
    sales_parameter_semantics: dict[str, Any],
    retail_parameter_semantics: dict[str, Any],
    reconciliation: dict[str, Any],
    consistency_checks: list[dict[str, Any]],
) -> list[str]:
    issues: list[str] = []
    if not join_analysis.get("sale_no_head_line_link_stable"):
        issues.append("sale_no 头行关联仍不稳定，暂不进入正式 sales_orders / sales_order_items 映射")
    for join_key in join_analysis.get("candidate_keys", []):
        if join_key.get("key") in {"sale_date", "operator"} and not join_key.get("stable_candidate"):
            issues.append(f"{join_key['key']} 当前不能作为稳定头行关联键")
    if sales_parameter_semantics.get("parameter.Depart", {}).get("semantics") == "insufficient_evidence":
        issues.append("销售清单 parameter.Depart 的范围语义仍未确认")
    if sales_parameter_semantics.get("parameter.BeginDate", {}).get("semantics") == "insufficient_evidence":
        issues.append("销售清单 parameter.BeginDate 的日期边界语义仍需更多证据")
    if sales_parameter_semantics.get("parameter.EndDate", {}).get("semantics") == "insufficient_evidence":
        issues.append("销售清单 parameter.EndDate 的日期边界语义仍需更多证据")
    for path, result in {**sales_parameter_semantics, **retail_parameter_semantics}.items():
        if not result.get("mainline_ready"):
            issues.append(f"{path} 当前未收口到正式 HTTP 主链参数")
    if retail_parameter_semantics.get("page", {}).get("semantics") != "pagination_page_switch":
        issues.append("零售明细统计 page 参数的分页语义未稳定确认")
    if retail_parameter_semantics.get("edate", {}).get("semantics") == "insufficient_evidence":
        issues.append("零售明细统计日期压缩后的范围收窄结论仍需补证")
    for metric in reconciliation.get("metrics", []):
        if metric.get("status") == "差异待解释":
            issues.append(f"对账指标 {metric.get('metric')} 仍是差异待解释")
    for check in consistency_checks:
        if check["status"] == "inconsistent_pending_explanation":
            issues.append(f"页面研究与 HTTP 回证不一致：{check['name']}")
    return sorted(set(issues))


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 Yeusoft 销售主线的页面研究 + 纯 HTTP 回证证据闭环。")
    parser.add_argument("--readme", default=str(README_PATH), help="账号说明文件路径")
    parser.add_argument("--report-doc", default=str(DEFAULT_REPORT_DOC_PATH), help="report_api_samples.md 路径")
    parser.add_argument("--page-research", help="指定页面研究汇总 JSON；默认使用最新的 yeusoft-page-research-*.json")
    parser.add_argument("--transport", choices=["curl", "urllib"], default="curl", help="HTTP 回证传输实现")
    parser.add_argument("--output", help="输出 JSON 文件路径；默认写入 tmp/capture-samples/analysis")
    args = parser.parse_args()

    readme = Path(args.readme)
    report_doc = Path(args.report_doc)
    page_research_path, page_research_payload = find_latest_page_research_summary(
        Path(args.page_research) if args.page_research else None,
        required_titles=("销售清单", "零售明细统计"),
    )
    output_path = (
        Path(args.output)
        if args.output
        else DEFAULT_OUTPUT_ROOT / f"sales-evidence-chain-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    )

    auth = read_login_auth(readme)
    access_token, _ = refresh_session_access_token(auth)
    api_base_url = auth.raw_login_data.get("JyApiUrl") if auth.raw_login_data else auth.api_base_url

    sales_list_spec = find_report_spec_by_title(report_doc, "销售清单")
    retail_detail_spec = find_report_spec_by_title(report_doc, "零售明细统计")
    if sales_list_spec is None or retail_detail_spec is None:
        raise RuntimeError("未在 report_api_samples.md 中找到 销售清单 或 零售明细统计")
    if not isinstance(sales_list_spec.payload, dict) or not isinstance(retail_detail_spec.payload, dict):
        raise RuntimeError("销售清单/零售明细统计 payload 必须是 JSON object")

    grid_1_payload = {"menuid": SALES_MENU_ID, "gridid": f"{SALES_MENU_ID}_1", "isJyApi": True}
    grid_2_payload = {"menuid": SALES_MENU_ID, "gridid": f"{SALES_MENU_ID}_2", "isJyApi": True}
    grid_1_url, grid_1_data, _ = post_with_auth(
        url=GRID_VIEW_URL,
        payload=grid_1_payload,
        api_base_url=api_base_url,
        access_token=access_token,
        transport=args.transport,
    )
    grid_2_url, grid_2_data, _ = post_with_auth(
        url=GRID_VIEW_URL,
        payload=grid_2_payload,
        api_base_url=api_base_url,
        access_token=access_token,
        transport=args.transport,
    )
    document_url, document_data, document_analysis = post_with_auth(
        url=SALES_REPORT_URL,
        payload=DEFAULT_SALE_REPORT_PAYLOAD,
        api_base_url=api_base_url,
        access_token=access_token,
        transport=args.transport,
    )
    detail_url, detail_data, detail_analysis = post_with_auth(
        url=sales_list_spec.url,
        payload=sales_list_spec.payload,
        api_base_url=api_base_url,
        access_token=access_token,
        transport=args.transport,
    )

    grain_analysis = build_sales_menu_grain_analysis(
        menuid=SALES_MENU_ID,
        document_grid_payload=grid_1_data,
        detail_grid_payload=grid_2_data,
        document_data_payload=document_data,
        detail_data_payload=detail_data,
    )
    join_analysis = build_sales_head_line_join_analysis(
        document_payload=document_data,
        detail_payload=detail_data,
    )

    sales_http_probes: dict[str, dict[str, Any]] = {}
    sales_probe_variants: dict[str, list[dict[str, Any]]] = {
        "parameter.Tiem": [],
        "parameter.BeginDate": [],
        "parameter.EndDate": [],
        "parameter.Depart": [],
    }
    sales_probe_definitions = [
        ("parameter.Tiem", "0"),
        ("parameter.Tiem", "1"),
        ("parameter.Tiem", "2"),
        ("parameter.BeginDate", sales_list_spec.payload["parameter"]["EndDate"]),
        ("parameter.EndDate", sales_list_spec.payload["parameter"]["BeginDate"]),
        ("parameter.Depart", ""),
    ]
    for parameter_path, parameter_value in sales_probe_definitions:
        probe_payload = build_variant_payload(sales_list_spec.payload, parameter_path, parameter_value)
        probe_url, probe_data, probe_analysis = post_with_auth(
            url=sales_list_spec.url,
            payload=probe_payload,
            api_base_url=api_base_url,
            access_token=access_token,
            transport=args.transport,
        )
        key = f"{parameter_path}={parameter_value}"
        sales_http_probes[key] = {
            "url": probe_url,
            "payload": probe_payload,
            "analysis": probe_analysis,
        }
        sales_probe_variants[parameter_path].append({"value": parameter_value, **probe_analysis})

    sales_parameter_semantics = {
        path: classify_http_probe_semantics(
            parameter_path=path,
            baseline_analysis=detail_analysis,
            variants=variants,
        )
        for path, variants in sales_probe_variants.items()
    }

    retail_base_page_payload = build_retail_detail_page_payload(retail_detail_spec.payload, page_no=0, page_size=20)
    retail_page_1_payload = build_retail_detail_page_payload(retail_detail_spec.payload, page_no=1, page_size=20)
    retail_aligned_end_payload = build_variant_payload(
        retail_base_page_payload,
        "edate",
        sales_list_spec.payload["parameter"]["EndDate"],
    )
    retail_same_day_payload = build_variant_payload(retail_base_page_payload, "edate", retail_detail_spec.payload["bdate"])

    retail_base_url, retail_base_data, retail_base_analysis = post_with_auth(
        url=retail_detail_spec.url,
        payload=retail_base_page_payload,
        api_base_url=api_base_url,
        access_token=access_token,
        transport=args.transport,
    )
    retail_page_1_url, retail_page_1_data, retail_page_1_analysis = post_with_auth(
        url=retail_detail_spec.url,
        payload=retail_page_1_payload,
        api_base_url=api_base_url,
        access_token=access_token,
        transport=args.transport,
    )
    retail_aligned_end_url, retail_aligned_end_data, retail_aligned_end_analysis = post_with_auth(
        url=retail_detail_spec.url,
        payload=retail_aligned_end_payload,
        api_base_url=api_base_url,
        access_token=access_token,
        transport=args.transport,
    )
    retail_same_day_url, retail_same_day_data, retail_same_day_analysis = post_with_auth(
        url=retail_detail_spec.url,
        payload=retail_same_day_payload,
        api_base_url=api_base_url,
        access_token=access_token,
        transport=args.transport,
    )

    retail_parameter_semantics = {
        "page": classify_http_probe_semantics(
            parameter_path="page",
            baseline_analysis=retail_base_analysis,
            variants=[{"value": 1, **retail_page_1_analysis}],
        ),
        "edate": classify_http_probe_semantics(
            parameter_path="edate",
            baseline_analysis=retail_base_analysis,
            variants=[{"value": retail_aligned_end_payload["edate"], **retail_aligned_end_analysis}],
        ),
    }

    retail_pagination_result = fetch_retail_detail_pages(
        retail_detail_spec.payload,
        lambda request_payload: perform_request(
            args.transport,
            maybe_override_url(_make_spec(retail_detail_spec.url), api_base_url),
            request_payload,
            build_report_auth_headers(maybe_override_url(_make_spec(retail_detail_spec.url), api_base_url), access_token),
        ),
        page_size=20,
    )
    reconciliation = build_sales_reconciliation_report(
        retail_pages=retail_pagination_result,
        sales_list_payload=detail_data,
        retail_request_payload=retail_base_page_payload,
        sales_request_payload=sales_list_spec.payload,
    )

    sales_page_summary = get_page_summary(page_research_payload, "销售清单")
    retail_page_summary = get_page_summary(page_research_payload, "零售明细统计")
    consistency_checks = [
        compare_page_research_to_http(
            name="grain_route",
            page_research_value=sales_page_summary.get("grain_route"),
            http_value=(
                "multi_grain_route"
                if grain_analysis["conclusion"]["document_variant_kind"] == "document_header_candidate"
                and grain_analysis["conclusion"]["detail_variant_kind"] == "line_detail_candidate"
                else "single_route"
            ),
        ),
        compare_page_research_to_http(
            name="candidate_join_key.sale_no",
            page_research_value="sale_no" in (sales_page_summary.get("candidate_join_keys") or []),
            http_value=join_analysis.get("sale_no_head_line_link_stable"),
        ),
        compare_page_research_to_http(
            name="parameter.Tiem",
            page_research_value=(sales_page_summary.get("parameter_semantics") or {}).get("parameter.Tiem", {}).get("semantics"),
            http_value=sales_parameter_semantics["parameter.Tiem"]["semantics"],
        ),
        compare_page_research_to_http(
            name="parameter.BeginDate",
            page_research_value=(sales_page_summary.get("parameter_semantics") or {}).get("parameter.BeginDate", {}).get("semantics"),
            http_value=sales_parameter_semantics["parameter.BeginDate"]["semantics"],
        ),
        compare_page_research_to_http(
            name="parameter.EndDate",
            page_research_value=(sales_page_summary.get("parameter_semantics") or {}).get("parameter.EndDate", {}).get("semantics"),
            http_value=sales_parameter_semantics["parameter.EndDate"]["semantics"],
        ),
        compare_page_research_to_http(
            name="SelDeptSaleList.page",
            page_research_value=(retail_page_summary.get("parameter_semantics") or {}).get("page", {}).get("semantics"),
            http_value=retail_parameter_semantics["page"]["semantics"],
        ),
        compare_page_research_to_http(
            name="SelDeptSaleList.edate",
            page_research_value=(retail_page_summary.get("parameter_semantics") or {}).get("edate", {}).get("semantics"),
            http_value=retail_parameter_semantics["edate"]["semantics"],
        ),
    ]

    issue_flags = build_issue_flags(
        join_analysis=join_analysis,
        sales_parameter_semantics=sales_parameter_semantics,
        retail_parameter_semantics=retail_parameter_semantics,
        reconciliation=reconciliation,
        consistency_checks=consistency_checks,
    )

    output = {
        "fetched_at": now_local().isoformat(),
        "auth_context": {
            "company_code": auth.company_code,
            "dept_code": auth.dept_code,
            "dept_name": auth.dept_name,
            "user_name": auth.user_name,
        },
        "page_research_reference": {
            "path": str(page_research_path),
            "sales_page_summary": {
                "title": sales_page_summary.get("title"),
                "grain_route": sales_page_summary.get("grain_route"),
                "candidate_join_keys": sales_page_summary.get("candidate_join_keys"),
                "parameter_semantics": sales_page_summary.get("parameter_semantics"),
            },
            "retail_detail_page_summary": {
                "title": retail_page_summary.get("title"),
                "grain_route": retail_page_summary.get("grain_route"),
                "parameter_semantics": retail_page_summary.get("parameter_semantics"),
            },
        },
        "requests": {
            "grid_1": {"url": grid_1_url, "payload": grid_1_payload},
            "grid_2": {"url": grid_2_url, "payload": grid_2_payload},
            "document_route": {"url": document_url, "payload": DEFAULT_SALE_REPORT_PAYLOAD},
            "detail_route": {"url": detail_url, "payload": sales_list_spec.payload},
            "retail_detail_page_0": {"url": retail_base_url, "payload": retail_base_page_payload},
            "retail_detail_page_1": {"url": retail_page_1_url, "payload": retail_page_1_payload},
            "retail_detail_aligned_end": {"url": retail_aligned_end_url, "payload": retail_aligned_end_payload},
            "retail_detail_same_day": {"url": retail_same_day_url, "payload": retail_same_day_payload},
        },
        "route_pairing": grain_analysis,
        "join_key_analysis": join_analysis,
        "sales_http_verification": {
            "document_route": {
                "analysis": document_analysis,
            },
            "detail_route": {
                "analysis": detail_analysis,
            },
            "parameter_probes": sales_http_probes,
            "parameter_semantics": sales_parameter_semantics,
        },
        "retail_detail_http_verification": {
            "page_0": {"analysis": retail_base_analysis, "payload": retail_base_page_payload},
            "page_1": {"analysis": retail_page_1_analysis, "payload": retail_page_1_payload},
            "aligned_end": {"analysis": retail_aligned_end_analysis, "payload": retail_aligned_end_payload},
            "same_day": {"analysis": retail_same_day_analysis, "payload": retail_same_day_payload},
            "parameter_semantics": retail_parameter_semantics,
            "edge_case_notes": [
                {
                    "parameter_path": "edate",
                    "value": retail_same_day_payload["edate"],
                    "analysis": retail_same_day_analysis,
                    "note": "当 edate 压缩到与 bdate 同一天时，零售明细统计会退化成单行结果，属于单日 edge case。",
                }
            ],
            "pagination_summary": serialize_retail_detail_pagination_result(retail_pagination_result),
        },
        "reconciliation": reconciliation,
        "consistency_checks": consistency_checks,
        "issue_flags": issue_flags,
        "conclusion": {
            "document_header_candidate_source": "SelSaleReport",
            "line_detail_candidate_source": "GetDIYReportData(menuid=E004001008,gridid=E004001008_2)",
            "retail_detail_role": "research_and_reconciliation_only",
            "confirmed_http_mainline_parameters": [
                {
                    "path": path,
                    "semantics": result["semantics"],
                    "recommended_http_strategy": result["recommended_http_strategy"],
                }
                for path, result in {
                    **sales_parameter_semantics,
                    **retail_parameter_semantics,
                }.items()
                if result["mainline_ready"]
            ],
            "followup_parameters": [
                {
                    "path": path,
                    "semantics": result["semantics"],
                    "recommended_http_strategy": result["recommended_http_strategy"],
                }
                for path, result in {
                    **sales_parameter_semantics,
                    **retail_parameter_semantics,
                }.items()
                if not result["mainline_ready"]
            ],
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({"ok": True, "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
