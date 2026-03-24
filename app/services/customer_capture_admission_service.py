from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.capture.persist_helpers import append_capture_payload


CUSTOMER_MASTER_RECORDS_ENDPOINT = "customer_master_records"
CUSTOMER_MASTER_ROUTE_KIND = "master"


def build_customer_capture_research_bundle(
    *,
    customer_page_record: Mapping[str, Any],
    blocking_issues: list[str] | None = None,
    baseline_row_count: int | None = None,
) -> dict[str, Any]:
    payload_hints = dict((customer_page_record.get("payload_hints") or {}))
    endpoint_summaries = list(customer_page_record.get("endpoint_summaries") or [])
    max_row_count = 0
    if endpoint_summaries:
        max_row_count = int(endpoint_summaries[0].get("max_row_count") or 0)
    if baseline_row_count is not None:
        max_row_count = int(baseline_row_count)
    effective_blockers = list(blocking_issues or ["尚未完成单变量探测", "尚未完成 HTTP 回证"])
    return {
        "customer_list": {
            "capture_route_name": CUSTOMER_MASTER_RECORDS_ENDPOINT,
            "capture_role": "mainline_fact",
            "route_kind": "raw",
            "capture_parameter_plan": {
                "default_deptname": "",
                "baseline_page": 1,
                "baseline_pagesize": 20,
                "page_mode": "sequential_pagination",
                "search_fields": ["deptname"],
                "pagination_fields": list(payload_hints.get("pagination_fields") or ["page", "pagesize"]),
                "baseline_row_count": max_row_count,
            },
            "capture_admission_ready": False,
            "blocking_issues": effective_blockers,
            "research_only": True,
        }
    }


def build_customer_capture_admission_bundle(
    *,
    customer_evidence: Mapping[str, Any],
    baseline_payload: dict[str, Any] | list[Any],
    baseline_request_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    customer_list = dict((customer_evidence.get("customer_list") or {}))
    capture_parameter_plan = dict((customer_list.get("capture_parameter_plan") or {}))
    blocking_issues = list(customer_list.get("blocking_issues") or [])
    observed_total_rows = int(((customer_list.get("baseline") or {}).get("row_count") or 0))
    capture_admission_ready = bool(customer_list.get("capture_admission_ready")) and not blocking_issues
    return {
        "customer_list": {
            "capture_route_name": CUSTOMER_MASTER_RECORDS_ENDPOINT,
            "capture_role": "mainline_fact",
            "route_kind": CUSTOMER_MASTER_ROUTE_KIND,
            "capture_parameter_plan": capture_parameter_plan,
            "capture_admission_ready": capture_admission_ready,
            "blocking_issues": blocking_issues,
            "research_only": False,
            "capture_page_summary": {
                "request_payload": dict(baseline_request_payload or {}),
                "observed_total_rows": observed_total_rows,
                "empty_dataset_confirmed": bool(capture_parameter_plan.get("empty_dataset_confirmed")),
                "capture_complete": True,
            },
        }
    }


def persist_customer_capture_research_bundle(
    *,
    capture_batch_id: str,
    customer_page_record: Mapping[str, Any],
    blocking_issues: list[str] | None,
    baseline_payload: dict[str, Any] | list[Any],
    baseline_request_payload: dict[str, Any] | None,
    source_endpoint: str,
    account_context: dict[str, Any] | None = None,
    baseline_row_count: int | None = None,
) -> dict[str, Any]:
    bundle = build_customer_capture_research_bundle(
        customer_page_record=customer_page_record,
        blocking_issues=blocking_issues,
        baseline_row_count=baseline_row_count,
    )
    customer_list = dict(bundle["customer_list"])

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
        source_endpoint=CUSTOMER_MASTER_RECORDS_ENDPOINT,
        route_kind="raw",
        payload=baseline_payload,
        request_params={
            "route_kind": "raw",
            "account_context": account_context,
            "request_payload": baseline_request_payload,
            "upstream_source_endpoint": source_endpoint,
            "capture_parameter_plan": customer_list["capture_parameter_plan"],
            "blocking_issues": customer_list["blocking_issues"],
            "research_only": customer_list["research_only"],
        },
        page_no=10,
    )
    return bundle


def persist_customer_capture_admission_bundle(
    *,
    capture_batch_id: str,
    customer_evidence: Mapping[str, Any],
    baseline_payload: dict[str, Any] | list[Any],
    baseline_request_payload: dict[str, Any] | None,
    source_endpoint: str,
    account_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = build_customer_capture_admission_bundle(
        customer_evidence=customer_evidence,
        baseline_payload=baseline_payload,
        baseline_request_payload=baseline_request_payload,
    )
    customer_list = dict(bundle["customer_list"])
    if not customer_list["capture_admission_ready"]:
        raise ValueError("客户资料 capture 准入条件未满足: " + "；".join(customer_list["blocking_issues"]))

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
        page_no=0,
    )
    append_capture_payload(
        capture_batch_id,
        source_endpoint=CUSTOMER_MASTER_RECORDS_ENDPOINT,
        route_kind=CUSTOMER_MASTER_ROUTE_KIND,
        payload=baseline_payload,
        request_params={
            "route_kind": CUSTOMER_MASTER_ROUTE_KIND,
            "account_context": account_context,
            "request_payload": baseline_request_payload,
            "upstream_source_endpoint": source_endpoint,
            "capture_parameter_plan": customer_list["capture_parameter_plan"],
            "capture_page_summary": customer_list["capture_page_summary"],
        },
        page_no=100,
    )
    return bundle
