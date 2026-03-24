from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.capture.persist_helpers import append_capture_payload


DAILY_PAYMENT_SNAPSHOT_RECORDS_ENDPOINT = "daily_payment_slips_snapshot"
DAILY_PAYMENT_SNAPSHOT_ROUTE_KIND = "snapshot"


def build_daily_payment_snapshot_capture_admission_bundle(
    *,
    daily_payment_snapshot_evidence: Mapping[str, Any],
    baseline_payload: dict[str, Any] | list[Any],
    baseline_request_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    snapshot_detail = dict((daily_payment_snapshot_evidence.get("daily_payment_snapshot") or {}))
    capture_parameter_plan = dict((snapshot_detail.get("capture_parameter_plan") or {}))
    capture_page_summary = dict((snapshot_detail.get("capture_page_summary") or {}))
    blocking_issues = list(snapshot_detail.get("blocking_issues") or [])
    capture_admission_ready = bool(snapshot_detail.get("capture_admission_ready")) and not blocking_issues
    return {
        "daily_payment_snapshot": {
            "capture_route_name": DAILY_PAYMENT_SNAPSHOT_RECORDS_ENDPOINT,
            "capture_role": "snapshot",
            "route_kind": DAILY_PAYMENT_SNAPSHOT_ROUTE_KIND,
            "capture_parameter_plan": capture_parameter_plan,
            "capture_admission_ready": capture_admission_ready,
            "blocking_issues": blocking_issues,
            "research_only": False,
            "capture_page_summary": {
                **capture_page_summary,
                "request_payload": dict(baseline_request_payload or capture_page_summary.get("request_payload") or {}),
            },
        }
    }


def persist_daily_payment_snapshot_capture_admission_bundle(
    *,
    capture_batch_id: str,
    daily_payment_snapshot_evidence: Mapping[str, Any],
    baseline_payload: dict[str, Any] | list[Any],
    baseline_request_payload: dict[str, Any] | None,
    source_endpoint: str,
    account_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = build_daily_payment_snapshot_capture_admission_bundle(
        daily_payment_snapshot_evidence=daily_payment_snapshot_evidence,
        baseline_payload=baseline_payload,
        baseline_request_payload=baseline_request_payload,
    )
    snapshot_detail = dict(bundle["daily_payment_snapshot"])
    if not snapshot_detail["capture_admission_ready"]:
        raise ValueError("每日流水单 snapshot capture 条件未满足: " + "；".join(snapshot_detail["blocking_issues"]))

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
        source_endpoint=DAILY_PAYMENT_SNAPSHOT_RECORDS_ENDPOINT,
        route_kind=DAILY_PAYMENT_SNAPSHOT_ROUTE_KIND,
        payload=baseline_payload,
        request_params={
            "route_kind": DAILY_PAYMENT_SNAPSHOT_ROUTE_KIND,
            "account_context": account_context,
            "request_payload": baseline_request_payload,
            "upstream_source_endpoint": source_endpoint,
            "capture_parameter_plan": snapshot_detail["capture_parameter_plan"],
            "capture_page_summary": snapshot_detail["capture_page_summary"],
        },
        page_no=100,
    )
    return bundle
