from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.capture.persist_helpers import append_capture_payload


MEMBER_MAINTENANCE_RECORDS_ENDPOINT = "member_maintenance_records"
MEMBER_MAINTENANCE_ROUTE_KIND = "master"


def build_member_maintenance_capture_research_bundle(
    *,
    member_maintenance_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    detail = dict((member_maintenance_evidence.get("member_maintenance") or {}))
    capture_parameter_plan = dict((detail.get("capture_parameter_plan") or {}))
    blocking_issues = list(detail.get("blocking_issues") or [])
    return {
        "member_maintenance": {
            "capture_route_name": MEMBER_MAINTENANCE_RECORDS_ENDPOINT,
            "capture_role": "mainline_fact",
            "route_kind": "raw",
            "capture_parameter_plan": capture_parameter_plan,
            "capture_admission_ready": bool(detail.get("capture_admission_ready")),
            "blocking_issues": blocking_issues,
            "research_only": True,
        }
    }


def build_member_maintenance_capture_admission_bundle(
    *,
    member_maintenance_evidence: Mapping[str, Any],
    baseline_payload: dict[str, Any] | list[Any],
    baseline_request_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    detail = dict((member_maintenance_evidence.get("member_maintenance") or {}))
    capture_parameter_plan = dict((detail.get("capture_parameter_plan") or {}))
    blocking_issues = list(detail.get("blocking_issues") or [])
    observed_total_rows = int(((detail.get("baseline") or {}).get("row_count") or 0))
    capture_admission_ready = bool(detail.get("capture_admission_ready")) and not blocking_issues
    return {
        "member_maintenance": {
            "capture_route_name": MEMBER_MAINTENANCE_RECORDS_ENDPOINT,
            "capture_role": "mainline_fact",
            "route_kind": MEMBER_MAINTENANCE_ROUTE_KIND,
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


def persist_member_maintenance_capture_research_bundle(
    *,
    capture_batch_id: str,
    member_maintenance_evidence: Mapping[str, Any],
    baseline_payload: dict[str, Any] | list[Any],
    baseline_request_payload: dict[str, Any] | None,
    source_endpoint: str,
    account_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = build_member_maintenance_capture_research_bundle(
        member_maintenance_evidence=member_maintenance_evidence
    )
    member_maintenance = dict(bundle["member_maintenance"])

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
        source_endpoint=MEMBER_MAINTENANCE_RECORDS_ENDPOINT,
        route_kind="raw",
        payload=baseline_payload,
        request_params={
            "route_kind": "raw",
            "account_context": account_context,
            "request_payload": baseline_request_payload,
            "upstream_source_endpoint": source_endpoint,
            "capture_parameter_plan": member_maintenance["capture_parameter_plan"],
            "blocking_issues": member_maintenance["blocking_issues"],
            "research_only": member_maintenance["research_only"],
        },
        page_no=10,
    )
    return bundle


def persist_member_maintenance_capture_admission_bundle(
    *,
    capture_batch_id: str,
    member_maintenance_evidence: Mapping[str, Any],
    baseline_payload: dict[str, Any] | list[Any],
    baseline_request_payload: dict[str, Any] | None,
    source_endpoint: str,
    account_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = build_member_maintenance_capture_admission_bundle(
        member_maintenance_evidence=member_maintenance_evidence,
        baseline_payload=baseline_payload,
        baseline_request_payload=baseline_request_payload,
    )
    member_maintenance = dict(bundle["member_maintenance"])
    if not member_maintenance["capture_admission_ready"]:
        raise ValueError("会员维护 capture 准入条件未满足: " + "；".join(member_maintenance["blocking_issues"]))

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
        source_endpoint=MEMBER_MAINTENANCE_RECORDS_ENDPOINT,
        route_kind=MEMBER_MAINTENANCE_ROUTE_KIND,
        payload=baseline_payload,
        request_params={
            "route_kind": MEMBER_MAINTENANCE_ROUTE_KIND,
            "account_context": account_context,
            "request_payload": baseline_request_payload,
            "upstream_source_endpoint": source_endpoint,
            "capture_parameter_plan": member_maintenance["capture_parameter_plan"],
            "capture_page_summary": member_maintenance["capture_page_summary"],
        },
        page_no=100,
    )
    return bundle
