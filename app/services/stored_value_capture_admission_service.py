from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.capture.persist_helpers import append_capture_payload
from app.services.erp_research_service import extract_normalized_table_rows


STORED_VALUE_CARD_DETAIL_ENDPOINT = "stored_value_card_detail"
STORED_VALUE_CARD_DETAIL_ROUTE_KIND = "detail"


def build_stored_value_capture_research_bundle(
    *,
    stored_value_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    detail = dict((stored_value_evidence.get("stored_value_detail") or {}))
    capture_parameter_plan = dict((detail.get("capture_parameter_plan") or {}))
    blocking_issues = list(detail.get("blocking_issues") or [])
    return {
        "stored_value_detail": {
            "capture_route_name": STORED_VALUE_CARD_DETAIL_ENDPOINT,
            "capture_role": "mainline_fact",
            "route_kind": "raw",
            "capture_parameter_plan": capture_parameter_plan,
            "capture_admission_ready": bool(detail.get("capture_admission_ready")),
            "blocking_issues": blocking_issues,
            "research_only": True,
        }
    }


def build_stored_value_capture_admission_bundle(
    *,
    stored_value_evidence: Mapping[str, Any],
    baseline_payload: dict[str, Any] | list[Any],
    baseline_request_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    detail = dict((stored_value_evidence.get("stored_value_detail") or {}))
    capture_parameter_plan = dict((detail.get("capture_parameter_plan") or {}))
    blocking_issues = list(detail.get("blocking_issues") or [])
    observed_total_rows = len(extract_normalized_table_rows(baseline_payload))
    date_partition_verification = dict((detail.get("date_partition_verification") or {}))
    search_behavior = dict((detail.get("search_behavior") or {}))
    capture_admission_ready = bool(detail.get("capture_admission_ready")) and not blocking_issues
    return {
        "stored_value_detail": {
            "capture_route_name": STORED_VALUE_CARD_DETAIL_ENDPOINT,
            "capture_role": "mainline_fact",
            "route_kind": STORED_VALUE_CARD_DETAIL_ROUTE_KIND,
            "capture_parameter_plan": capture_parameter_plan,
            "capture_admission_ready": capture_admission_ready,
            "blocking_issues": blocking_issues,
            "research_only": False,
            "capture_page_summary": {
                "request_payload": dict(baseline_request_payload or {}),
                "observed_total_rows": observed_total_rows,
                "capture_complete": bool(date_partition_verification.get("partition_union_matches_baseline")),
                "date_partition_mode": date_partition_verification.get("partition_mode"),
                "date_partition_verified": bool(date_partition_verification.get("partition_union_matches_baseline")),
                "supported_search_groups": list(search_behavior.get("supported_search_groups") or []),
            },
        }
    }


def persist_stored_value_capture_research_bundle(
    *,
    capture_batch_id: str,
    stored_value_evidence: Mapping[str, Any],
    baseline_payload: dict[str, Any] | list[Any],
    baseline_request_payload: dict[str, Any] | None,
    source_endpoint: str,
    account_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = build_stored_value_capture_research_bundle(stored_value_evidence=stored_value_evidence)
    stored_value_detail = dict(bundle["stored_value_detail"])

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
        source_endpoint=STORED_VALUE_CARD_DETAIL_ENDPOINT,
        route_kind="raw",
        payload=baseline_payload,
        request_params={
            "route_kind": "raw",
            "account_context": account_context,
            "request_payload": baseline_request_payload,
            "upstream_source_endpoint": source_endpoint,
            "capture_parameter_plan": stored_value_detail["capture_parameter_plan"],
            "blocking_issues": stored_value_detail["blocking_issues"],
            "research_only": stored_value_detail["research_only"],
        },
        page_no=10,
    )
    return bundle


def persist_stored_value_capture_admission_bundle(
    *,
    capture_batch_id: str,
    stored_value_evidence: Mapping[str, Any],
    baseline_payload: dict[str, Any] | list[Any],
    baseline_request_payload: dict[str, Any] | None,
    source_endpoint: str,
    account_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = build_stored_value_capture_admission_bundle(
        stored_value_evidence=stored_value_evidence,
        baseline_payload=baseline_payload,
        baseline_request_payload=baseline_request_payload,
    )
    stored_value_detail = dict(bundle["stored_value_detail"])
    if not stored_value_detail["capture_admission_ready"]:
        raise ValueError("储值卡明细 capture 准入条件未满足: " + "；".join(stored_value_detail["blocking_issues"]))

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
        source_endpoint=STORED_VALUE_CARD_DETAIL_ENDPOINT,
        route_kind=STORED_VALUE_CARD_DETAIL_ROUTE_KIND,
        payload=baseline_payload,
        request_params={
            "route_kind": STORED_VALUE_CARD_DETAIL_ROUTE_KIND,
            "account_context": account_context,
            "request_payload": baseline_request_payload,
            "upstream_source_endpoint": source_endpoint,
            "capture_parameter_plan": stored_value_detail["capture_parameter_plan"],
            "capture_page_summary": stored_value_detail["capture_page_summary"],
        },
        page_no=100,
    )
    return bundle
