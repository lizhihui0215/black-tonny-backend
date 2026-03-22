from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.batch_service import append_capture_payload
from app.services.product_evidence_service import extract_declared_total_count


PRODUCT_MASTER_RECORDS_ENDPOINT = "product_master_records"
PRODUCT_MASTER_ROUTE_KIND = "master"


def build_product_capture_research_bundle(
    *,
    product_page_record: Mapping[str, Any],
    blocking_issues: list[str] | None = None,
) -> dict[str, Any]:
    payload_hints = dict((product_page_record.get("payload_hints") or {}))
    endpoint_summaries = list(product_page_record.get("endpoint_summaries") or [])
    max_row_count = 0
    if endpoint_summaries:
        max_row_count = int(endpoint_summaries[0].get("max_row_count") or 0)
    effective_blockers = list(blocking_issues or ["尚未完成单变量探测", "尚未完成 HTTP 回证"])
    return {
        "product_list": {
            "capture_route_name": PRODUCT_MASTER_RECORDS_ENDPOINT,
            "capture_role": "mainline_fact",
            "route_kind": "raw",
            "capture_parameter_plan": {
                "default_spenum": "",
                "default_warecause": "",
                "baseline_page": 1,
                "baseline_pagesize": max_row_count or 60,
                "page_mode": "sequential_pagination",
                "org_fields": list(payload_hints.get("org_fields") or []),
                "pagination_fields": list(payload_hints.get("pagination_fields") or []),
            },
            "capture_admission_ready": False,
            "blocking_issues": effective_blockers,
            "research_only": True,
        }
    }


def build_product_capture_admission_bundle(
    *,
    product_evidence: Mapping[str, Any],
    page_payloads: Mapping[int, dict[str, Any] | list[Any]],
    page_request_payloads: Mapping[int, dict[str, Any] | None],
) -> dict[str, Any]:
    product_list = dict((product_evidence.get("product_list") or {}))
    capture_parameter_plan = dict((product_list.get("capture_parameter_plan") or {}))
    blocking_issues = list(product_list.get("blocking_issues") or [])
    sorted_pages = sorted(page_payloads)
    if not sorted_pages:
        raise ValueError("商品资料 capture admission 至少需要一页 payload")

    page_summaries: list[dict[str, Any]] = []
    declared_total_count = None
    observed_total_rows = 0
    for page_no in sorted_pages:
        payload = page_payloads[page_no]
        row_count = len((payload.get("retdata") or [{}])[0].get("Data") or []) if isinstance(payload, dict) else 0
        observed_total_rows += row_count
        declared_total_count = declared_total_count or extract_declared_total_count(payload)
        page_summaries.append(
            {
                "page": page_no,
                "row_count": row_count,
                "request_payload": dict(page_request_payloads.get(page_no) or {}),
            }
        )

    if declared_total_count is not None and observed_total_rows < declared_total_count:
        blocking_issues.append(
            f"顺序翻页仅覆盖 {observed_total_rows} 行，低于服务端声明总数 {declared_total_count}"
        )

    capture_admission_ready = bool(product_list.get("capture_admission_ready")) and not blocking_issues
    return {
        "product_list": {
            "capture_route_name": PRODUCT_MASTER_RECORDS_ENDPOINT,
            "capture_role": "mainline_fact",
            "route_kind": PRODUCT_MASTER_ROUTE_KIND,
            "capture_parameter_plan": capture_parameter_plan,
            "capture_admission_ready": capture_admission_ready,
            "blocking_issues": blocking_issues,
            "research_only": False,
            "capture_page_summary": {
                "pages": page_summaries,
                "declared_total_count": declared_total_count,
                "observed_total_rows": observed_total_rows,
                "page_count": len(page_summaries),
                "capture_complete": declared_total_count is None or observed_total_rows >= declared_total_count,
            },
        }
    }


def persist_product_capture_research_bundle(
    *,
    capture_batch_id: str,
    product_page_record: Mapping[str, Any],
    blocking_issues: list[str] | None,
    baseline_payload: dict[str, Any] | list[Any],
    baseline_request_payload: dict[str, Any] | None,
    source_endpoint: str,
    account_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = build_product_capture_research_bundle(
        product_page_record=product_page_record,
        blocking_issues=blocking_issues,
    )
    product_list = dict(bundle["product_list"])

    append_capture_payload(
        capture_batch_id,
        source_endpoint=source_endpoint,
        route_kind="raw",
        payload=baseline_payload,
        request_params={
            "route_kind": "raw",
            "account_context": account_context,
            "request_payload": baseline_request_payload,
        },
        page_no=int((baseline_request_payload or {}).get("page") or 1),
    )
    append_capture_payload(
        capture_batch_id,
        source_endpoint=PRODUCT_MASTER_RECORDS_ENDPOINT,
        route_kind="raw",
        payload=baseline_payload,
        request_params={
            "route_kind": "raw",
            "account_context": account_context,
            "request_payload": baseline_request_payload,
            "upstream_source_endpoint": source_endpoint,
            "capture_parameter_plan": product_list["capture_parameter_plan"],
            "blocking_issues": product_list["blocking_issues"],
            "research_only": product_list["research_only"],
        },
        page_no=10,
    )
    return bundle


def persist_product_capture_admission_bundle(
    *,
    capture_batch_id: str,
    product_evidence: Mapping[str, Any],
    page_payloads: Mapping[int, dict[str, Any] | list[Any]],
    page_request_payloads: Mapping[int, dict[str, Any] | None],
    source_endpoint: str,
    account_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = build_product_capture_admission_bundle(
        product_evidence=product_evidence,
        page_payloads=page_payloads,
        page_request_payloads=page_request_payloads,
    )
    product_list = dict(bundle["product_list"])
    if not product_list["capture_admission_ready"]:
        raise ValueError("商品资料 capture 准入条件未满足: " + "；".join(product_list["blocking_issues"]))

    capture_page_summary = dict(product_list["capture_page_summary"])
    for index, page_no in enumerate(sorted(page_payloads)):
        payload = page_payloads[page_no]
        request_payload = page_request_payloads.get(page_no)
        append_capture_payload(
            capture_batch_id,
            source_endpoint=source_endpoint,
            route_kind="raw",
            payload=payload,
            request_params={
                "route_kind": "raw",
                "account_context": account_context,
                "request_payload": request_payload,
                "page": page_no,
            },
            page_no=index,
        )
        append_capture_payload(
            capture_batch_id,
            source_endpoint=PRODUCT_MASTER_RECORDS_ENDPOINT,
            route_kind=PRODUCT_MASTER_ROUTE_KIND,
            payload=payload,
            request_params={
                "route_kind": PRODUCT_MASTER_ROUTE_KIND,
                "account_context": account_context,
                "request_payload": request_payload,
                "upstream_source_endpoint": source_endpoint,
                "capture_parameter_plan": product_list["capture_parameter_plan"],
                "capture_page_summary": capture_page_summary,
                "page": page_no,
            },
            page_no=100 + index,
        )
    return bundle
