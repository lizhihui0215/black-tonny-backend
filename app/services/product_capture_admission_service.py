from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.batch_service import append_capture_payload


PRODUCT_MASTER_RECORDS_ENDPOINT = "product_master_records"


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
