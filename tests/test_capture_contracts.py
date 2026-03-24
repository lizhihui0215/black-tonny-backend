from __future__ import annotations

from app.db.base import capture_batches, capture_endpoint_payloads
from app.services.capture.contracts import (
    CAPTURE_BATCH_ALLOWED_STATUSES,
    CAPTURE_BATCH_COLUMNS,
    CAPTURE_BATCH_TABLE_NAME,
    CAPTURE_BATCH_STATUS_CAPTURED,
    CAPTURE_BATCH_STATUS_FAILED,
    CAPTURE_BATCH_STATUS_PARTIAL,
    CAPTURE_BATCH_STATUS_QUEUED,
    CAPTURE_BATCH_STATUS_TRANSFORMED,
    CAPTURE_ENDPOINT_PAYLOAD_COLUMNS,
    CAPTURE_ENDPOINT_PAYLOAD_TABLE_NAME,
    CAPTURE_ROUTE_REQUIRED_FIELDS,
    CAPTURE_ROUTE_ROLE_VALUES,
    CAPTURE_ROUTE_STATUS_VALUES,
)
from app.services.capture.route_registry import (
    CAPTURE_ROLE_LABELS,
    CAPTURE_STATUS_LABELS,
    build_capture_route_registry_from_board,
)
from app.services.capture.admissions import (
    build_inventory_capture_admission_bundle,
    build_sales_capture_admission_bundle,
)


def test_capture_table_contract_matches_current_schema() -> None:
    assert capture_batches.name == CAPTURE_BATCH_TABLE_NAME
    assert tuple(capture_batches.c.keys()) == CAPTURE_BATCH_COLUMNS

    assert capture_endpoint_payloads.name == CAPTURE_ENDPOINT_PAYLOAD_TABLE_NAME
    assert tuple(capture_endpoint_payloads.c.keys()) == CAPTURE_ENDPOINT_PAYLOAD_COLUMNS


def test_capture_batch_allowed_statuses_cover_runtime_status_values() -> None:
    assert CAPTURE_BATCH_ALLOWED_STATUSES == (
        CAPTURE_BATCH_STATUS_QUEUED,
        CAPTURE_BATCH_STATUS_CAPTURED,
        CAPTURE_BATCH_STATUS_PARTIAL,
        CAPTURE_BATCH_STATUS_FAILED,
        CAPTURE_BATCH_STATUS_TRANSFORMED,
    )


def test_capture_route_contract_values_match_registry_labels() -> None:
    assert tuple(CAPTURE_ROLE_LABELS.keys()) == CAPTURE_ROUTE_ROLE_VALUES
    assert tuple(CAPTURE_STATUS_LABELS.keys()) == CAPTURE_ROUTE_STATUS_VALUES


def test_capture_route_registry_entries_expose_required_contract_fields() -> None:
    board = {
        "summary": {"global_risk_map_complete": True},
        "entries": [
            {
                "domain": "sales",
                "domain_label": "销售",
                "route": "SelSaleReport",
                "title": "销售清单",
                "endpoint": "SelSaleReport",
                "menu_path": ["报表管理", "零售报表", "销售清单"],
                "source_kind": "主源候选",
                "stage": "已HTTP回证",
                "reliability_status": "中等可信",
                "research_map_complete": True,
                "mainline_ready": False,
                "blocking_issues": [],
                "next_action": "准备首批 capture 准入",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_parameter_plan": {},
                "capture_written_once": True,
                "latest_capture_batch_id": "sales-batch-001",
                "latest_capture_mode": "admission",
                "latest_capture_artifact": "tmp/capture-samples/analysis/sales-capture-admission.json",
            }
        ],
    }

    registry = build_capture_route_registry_from_board(board)
    entry = registry["routes"][0]
    assert set(CAPTURE_ROUTE_REQUIRED_FIELDS).issubset(entry)


def test_capture_admission_package_exposes_formal_entrypoints() -> None:
    assert callable(build_inventory_capture_admission_bundle)
    assert callable(build_sales_capture_admission_bundle)
