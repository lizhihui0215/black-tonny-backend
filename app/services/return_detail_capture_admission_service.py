from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.capture.persist_helpers import append_capture_payload


RETURN_DOCUMENT_LINES_ENDPOINT = "return_document_lines"
RETURN_DOCUMENT_LINES_ROUTE_KIND = "raw"


def build_return_detail_capture_research_bundle(
    *,
    return_detail_evidence: Mapping[str, Any],
    ui_probe_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    detail = dict((return_detail_evidence.get("return_detail") or {}))
    capture_parameter_plan = dict((detail.get("capture_parameter_plan") or {}))
    blocking_issues = list(detail.get("blocking_issues") or [])
    baseline = dict((detail.get("baseline") or {}))
    type_probe_summary = dict((detail.get("type_probe_summary") or {}))
    narrow_filter_probe_summary = dict((detail.get("narrow_filter_probe_summary") or {}))

    ui_probe_summary: dict[str, Any] = {}
    if ui_probe_payload:
        baseline_payload = dict((ui_probe_payload.get("baseline") or {}))
        ui_probe_summary = {
            "analysis_output": str(ui_probe_payload.get("_analysis_output") or ""),
            "post_data": baseline_payload.get("return_detail_post_data"),
            "component_found": bool((((baseline_payload.get("page_component_state_after_query") or {}).get("component_found")))),
            "table_ref_indexeddb_after_query": baseline_payload.get("table_ref_indexeddb_after_query"),
        }

    return {
        "return_detail": {
            "capture_route_name": RETURN_DOCUMENT_LINES_ENDPOINT,
            "capture_role": "mainline_fact",
            "route_kind": RETURN_DOCUMENT_LINES_ROUTE_KIND,
            "capture_parameter_plan": capture_parameter_plan,
            "capture_admission_ready": False,
            "blocking_issues": blocking_issues,
            "research_only": True,
            "baseline_analysis": baseline,
            "type_probe_summary": type_probe_summary,
            "narrow_filter_probe_summary": narrow_filter_probe_summary,
            "ui_probe_summary": ui_probe_summary,
        }
    }


def persist_return_detail_capture_research_bundle(
    *,
    capture_batch_id: str,
    return_detail_evidence: Mapping[str, Any],
    baseline_payload: dict[str, Any] | list[Any],
    baseline_request_payload: dict[str, Any] | None,
    source_endpoint: str,
    account_context: dict[str, Any] | None = None,
    ui_probe_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = build_return_detail_capture_research_bundle(
        return_detail_evidence=return_detail_evidence,
        ui_probe_payload=ui_probe_payload,
    )
    detail = dict(bundle["return_detail"])

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
        source_endpoint=RETURN_DOCUMENT_LINES_ENDPOINT,
        route_kind=RETURN_DOCUMENT_LINES_ROUTE_KIND,
        payload={
            "baseline_analysis": detail["baseline_analysis"],
            "type_probe_summary": detail["type_probe_summary"],
            "narrow_filter_probe_summary": detail["narrow_filter_probe_summary"],
            "ui_probe_summary": detail["ui_probe_summary"],
        },
        request_params={
            "route_kind": RETURN_DOCUMENT_LINES_ROUTE_KIND,
            "account_context": account_context,
            "request_payload": baseline_request_payload,
            "upstream_source_endpoint": source_endpoint,
            "capture_parameter_plan": detail["capture_parameter_plan"],
            "blocking_issues": detail["blocking_issues"],
            "research_only": detail["research_only"],
        },
        page_no=10,
    )
    return bundle
