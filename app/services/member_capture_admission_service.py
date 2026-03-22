from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.batch_service import append_capture_payload


MEMBER_PROFILE_RECORDS_ENDPOINT = "member_profile_records"


def build_member_capture_research_bundle(
    *,
    member_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    member_center = dict((member_evidence.get("member_center") or {}))
    parameter_semantics = dict((member_center.get("parameter_semantics") or {}))
    search_behavior = dict((member_center.get("search_behavior") or {}))
    return {
        "member_center": {
            "capture_route_name": MEMBER_PROFILE_RECORDS_ENDPOINT,
            "capture_role": "mainline_fact",
            "route_kind": "raw",
            "capture_parameter_plan": {
                "default_condition": "",
                "default_searchval": "",
                "default_VolumeNumber": "",
                "search_mode": "global_filter_when_condition_empty",
                "search_exact_examples": list(search_behavior.get("exact_match_values") or []),
                "volume_examples": [
                    item.get("value")
                    for item in (parameter_semantics.get("VolumeNumber") or {}).get("variants", [])
                ],
            },
            "capture_admission_ready": bool(member_center.get("capture_admission_ready")),
            "blocking_issues": list(member_center.get("blocking_issues") or []),
            "research_only": not bool(member_center.get("capture_admission_ready")),
        }
    }


def persist_member_capture_research_bundle(
    *,
    capture_batch_id: str,
    member_evidence: Mapping[str, Any],
    baseline_payload: dict[str, Any] | list[Any],
    baseline_request_payload: dict[str, Any] | None,
    source_endpoint: str,
    account_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = build_member_capture_research_bundle(member_evidence=member_evidence)
    member_center = dict(bundle["member_center"])

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
        source_endpoint=MEMBER_PROFILE_RECORDS_ENDPOINT,
        route_kind="raw",
        payload=baseline_payload,
        request_params={
            "route_kind": "raw",
            "account_context": account_context,
            "request_payload": baseline_request_payload,
            "upstream_source_endpoint": source_endpoint,
            "capture_parameter_plan": member_center["capture_parameter_plan"],
            "blocking_issues": member_center["blocking_issues"],
            "research_only": member_center["research_only"],
        },
        page_no=10,
    )
    return bundle
