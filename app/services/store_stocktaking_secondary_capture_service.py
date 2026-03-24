from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.capture.persist_helpers import append_capture_payload


STORE_STOCKTAKING_DIFF_RECORDS_ENDPOINT = "store_stocktaking_diff_records"
STORE_STOCKTAKING_DIFF_RECORDS_ROUTE_KIND = "diff"


def _find_probe_step(ui_probe_payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    for item in ui_probe_payload.get("component_method_probes") or []:
        if item.get("key") == key:
            return dict(item)
    return {}


def _snapshot_array_rows(step: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    snapshot = (((step.get("local_state_after") or {}).get("snapshot") or {}).get(key) or {})
    full_rows = snapshot.get("full_rows")
    if isinstance(full_rows, list):
        return [row for row in full_rows if isinstance(row, dict)]
    sample_rows = snapshot.get("sample_rows")
    if isinstance(sample_rows, list):
        return [row for row in sample_rows if isinstance(row, dict)]
    return []


def build_store_stocktaking_diff_capture_research_bundle(
    *,
    ui_probe_payload: Mapping[str, Any],
) -> dict[str, Any]:
    diff_step = _find_probe_step(ui_probe_payload, "component_method_getDiffData")
    summary_rows = _snapshot_array_rows(diff_step, "orderDiffHJData")
    diff_rows = _snapshot_array_rows(diff_step, "orderDiffData")
    diff_snapshot = (((diff_step.get("local_state_after") or {}).get("snapshot") or {}).get("orderDiffData") or {})
    summary_snapshot = (((diff_step.get("local_state_after") or {}).get("snapshot") or {}).get("orderDiffHJData") or {})

    blocking_issues: list[str] = []
    if not diff_rows:
        blocking_issues.append("当前 UI probe 尚未导出完整 orderDiffData，暂不能写入二级 research route")

    return {
        "store_stocktaking_diff": {
            "capture_route_name": STORE_STOCKTAKING_DIFF_RECORDS_ENDPOINT,
            "capture_role": "research",
            "route_kind": STORE_STOCKTAKING_DIFF_RECORDS_ROUTE_KIND,
            "capture_admission_ready": False,
            "research_only": True,
            "blocking_issues": blocking_issues,
            "diff_summary": {
                "order_diff_rows": int(diff_snapshot.get("length") or len(diff_rows)),
                "order_diff_summary_rows": int(summary_snapshot.get("length") or len(summary_rows)),
                "show_diff_page": bool((((diff_step.get("local_state_after") or {}).get("snapshot") or {}).get("showDiffPage"))),
                "component_method_key": diff_step.get("key"),
                "selected_item_keys": sorted(
                    set(
                        ((((diff_step.get("local_state_after") or {}).get("snapshot") or {}).get("selectItem") or {}).get("keys") or [])
                    )
                ),
            },
            "payload": {
                "orderDiffData": diff_rows,
                "orderDiffHJData": summary_rows,
            },
        }
    }


def persist_store_stocktaking_diff_capture_research_bundle(
    *,
    capture_batch_id: str,
    ui_probe_payload: Mapping[str, Any],
    source_endpoint: str,
    account_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = build_store_stocktaking_diff_capture_research_bundle(ui_probe_payload=ui_probe_payload)
    detail = dict(bundle["store_stocktaking_diff"])

    append_capture_payload(
        capture_batch_id,
        source_endpoint=source_endpoint,
        route_kind="raw",
        payload=dict(ui_probe_payload),
        request_params={
            "route_kind": "raw",
            "account_context": account_context,
            "research_only": True,
        },
        page_no=0,
    )
    append_capture_payload(
        capture_batch_id,
        source_endpoint=STORE_STOCKTAKING_DIFF_RECORDS_ENDPOINT,
        route_kind=STORE_STOCKTAKING_DIFF_RECORDS_ROUTE_KIND,
        payload=detail["payload"],
        request_params={
            "route_kind": STORE_STOCKTAKING_DIFF_RECORDS_ROUTE_KIND,
            "account_context": account_context,
            "upstream_source_endpoint": source_endpoint,
            "diff_summary": detail["diff_summary"],
            "blocking_issues": detail["blocking_issues"],
            "research_only": True,
        },
        page_no=10,
    )
    return bundle
