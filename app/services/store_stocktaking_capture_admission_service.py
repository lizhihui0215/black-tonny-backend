from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.capture.persist_helpers import append_capture_payload


STORE_STOCKTAKING_DOCUMENTS_ENDPOINT = "store_stocktaking_documents"
STORE_STOCKTAKING_DOCUMENTS_ROUTE_KIND = "document"


def _extract_rows(payload: dict[str, Any] | list[Any]) -> list[Any]:
    if not isinstance(payload, Mapping):
        return []
    data = payload.get("Data")
    if isinstance(data, Mapping):
        rows = data.get("Data")
        if isinstance(rows, list):
            return rows
    return []


def build_store_stocktaking_capture_research_bundle(
    *,
    stocktaking_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    detail = dict((stocktaking_evidence.get("store_stocktaking") or {}))
    capture_parameter_plan = dict((detail.get("capture_parameter_plan") or {}))
    blocking_issues = list(detail.get("blocking_issues") or [])
    return {
        "store_stocktaking": {
            "capture_route_name": STORE_STOCKTAKING_DOCUMENTS_ENDPOINT,
            "capture_role": "mainline_fact",
            "route_kind": "raw",
            "capture_parameter_plan": capture_parameter_plan,
            "capture_admission_ready": bool(detail.get("capture_admission_ready")),
            "blocking_issues": blocking_issues,
            "research_only": True,
        }
    }


def build_store_stocktaking_capture_admission_bundle(
    *,
    stocktaking_evidence: Mapping[str, Any],
    baseline_payload: dict[str, Any] | list[Any],
    baseline_request_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    detail = dict((stocktaking_evidence.get("store_stocktaking") or {}))
    capture_parameter_plan = dict((detail.get("capture_parameter_plan") or {}))
    blocking_issues = list(detail.get("blocking_issues") or [])
    capture_admission_ready = bool(detail.get("capture_admission_ready")) and not blocking_issues
    observed_total_rows = int(((detail.get("baseline") or {}).get("row_count") or 0))
    if not observed_total_rows:
        observed_total_rows = len(_extract_rows(baseline_payload))
    return {
        "store_stocktaking": {
            "capture_route_name": STORE_STOCKTAKING_DOCUMENTS_ENDPOINT,
            "capture_role": "mainline_fact",
            "route_kind": STORE_STOCKTAKING_DOCUMENTS_ROUTE_KIND,
            "capture_parameter_plan": capture_parameter_plan,
            "capture_admission_ready": capture_admission_ready,
            "blocking_issues": blocking_issues,
            "secondary_route_blocking_issues": list(detail.get("secondary_route_blocking_issues") or []),
            "research_only": False,
            "capture_page_summary": {
                "request_payload": dict(baseline_request_payload or {}),
                "observed_total_rows": observed_total_rows,
                "capture_complete": observed_total_rows > 0,
                "date_window_mode": capture_parameter_plan.get("date_window_mode"),
                "primary_stat_values": list(capture_parameter_plan.get("primary_stat_values") or []),
                "secondary_actions_pending": list(capture_parameter_plan.get("secondary_actions_pending") or []),
            },
        }
    }


def persist_store_stocktaking_capture_research_bundle(
    *,
    capture_batch_id: str,
    stocktaking_evidence: Mapping[str, Any],
    baseline_payload: dict[str, Any] | list[Any],
    baseline_request_payload: dict[str, Any] | None,
    source_endpoint: str,
    account_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = build_store_stocktaking_capture_research_bundle(stocktaking_evidence=stocktaking_evidence)
    store_stocktaking = dict(bundle["store_stocktaking"])

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
        source_endpoint=STORE_STOCKTAKING_DOCUMENTS_ENDPOINT,
        route_kind="raw",
        payload=baseline_payload,
        request_params={
            "route_kind": "raw",
            "account_context": account_context,
            "request_payload": baseline_request_payload,
            "upstream_source_endpoint": source_endpoint,
            "capture_parameter_plan": store_stocktaking["capture_parameter_plan"],
            "blocking_issues": store_stocktaking["blocking_issues"],
            "research_only": store_stocktaking["research_only"],
        },
        page_no=10,
    )
    return bundle


def persist_store_stocktaking_capture_admission_bundle(
    *,
    capture_batch_id: str,
    stocktaking_evidence: Mapping[str, Any],
    baseline_payload: dict[str, Any] | list[Any],
    baseline_request_payload: dict[str, Any] | None,
    source_endpoint: str,
    account_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = build_store_stocktaking_capture_admission_bundle(
        stocktaking_evidence=stocktaking_evidence,
        baseline_payload=baseline_payload,
        baseline_request_payload=baseline_request_payload,
    )
    store_stocktaking = dict(bundle["store_stocktaking"])
    if not store_stocktaking["capture_admission_ready"]:
        raise ValueError("门店盘点单 capture 准入条件未满足: " + "；".join(store_stocktaking["blocking_issues"]))

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
        source_endpoint=STORE_STOCKTAKING_DOCUMENTS_ENDPOINT,
        route_kind=STORE_STOCKTAKING_DOCUMENTS_ROUTE_KIND,
        payload=baseline_payload,
        request_params={
            "route_kind": STORE_STOCKTAKING_DOCUMENTS_ROUTE_KIND,
            "account_context": account_context,
            "request_payload": baseline_request_payload,
            "upstream_source_endpoint": source_endpoint,
            "capture_parameter_plan": store_stocktaking["capture_parameter_plan"],
            "capture_page_summary": store_stocktaking["capture_page_summary"],
            "secondary_route_blocking_issues": store_stocktaking["secondary_route_blocking_issues"],
        },
        page_no=100,
    )
    return bundle
