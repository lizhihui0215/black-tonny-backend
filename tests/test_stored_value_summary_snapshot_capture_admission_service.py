from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.core.config import clear_settings_cache
from app.db.base import capture_endpoint_payloads
from app.db.engine import clear_engine_caches
from app.services.stored_value_summary_snapshot_capture_admission_service import (
    STORED_VALUE_BY_STORE_SNAPSHOT_RECORDS_ENDPOINT,
    STORED_VALUE_CARD_SUMMARY_SNAPSHOT_RECORDS_ENDPOINT,
    STORED_VALUE_SUMMARY_SNAPSHOT_ROUTE_KIND,
    build_stored_value_by_store_snapshot_capture_admission_bundle,
    build_stored_value_card_summary_snapshot_capture_admission_bundle,
    persist_stored_value_by_store_snapshot_capture_admission_bundle,
    persist_stored_value_card_summary_snapshot_capture_admission_bundle,
)


def _configure_test_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CAPTURE_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'capture.db'}")
    monkeypatch.setenv("SERVING_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'serving.db'}")
    monkeypatch.setenv("PAYLOAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "sample"))
    clear_settings_cache()
    clear_engine_caches()


def _card_summary_evidence() -> dict[str, object]:
    return {
        "stored_value_card_summary_snapshot": {
            "capture_admission_ready": True,
            "blocking_issues": [],
            "capture_parameter_plan": {
                "default_menuid": "E004004004",
                "default_gridid": "E004004004_main",
                "default_begin_date": "2025-03-01",
                "default_end_date": "2026-04-01",
                "default_search": "",
                "page_mode": "single_request_page_field_ignored",
                "observed_total_rows": 2,
            },
            "capture_page_summary": {
                "request_payload": {
                    "menuid": "E004004004",
                    "gridid": "E004004004_main",
                    "parameter": {"BeginDate": "2025-03-01", "EndDate": "2026-04-01", "Search": ""},
                },
                "observed_total_rows": 2,
                "capture_complete": True,
            },
        }
    }


def _by_store_evidence() -> dict[str, object]:
    return {
        "stored_value_by_store_snapshot": {
            "capture_admission_ready": True,
            "blocking_issues": [],
            "capture_parameter_plan": {
                "default_menuid": "E004004003",
                "default_gridid": "E004004003_main",
                "default_begin_date": "2025-03-01",
                "default_end_date": "2026-04-01",
                "page_mode": "single_request_page_field_ignored",
                "observed_total_rows": 1,
            },
            "capture_page_summary": {
                "request_payload": {
                    "menuid": "E004004003",
                    "gridid": "E004004003_main",
                    "parameter": {"BeginDate": "2025-03-01", "EndDate": "2026-04-01"},
                },
                "observed_total_rows": 1,
                "capture_complete": True,
            },
        }
    }


def _card_payload() -> dict[str, object]:
    return {"errcode": "1000", "retdata": [{"VipCardID": "V001", "Balance": 299.0}, {"VipCardID": "V002", "Balance": 199.0}]}


def _by_store_payload() -> dict[str, object]:
    return {"errcode": "1000", "retdata": [{"DeptCode": "A0190248", "Balance": 999.0}]}


def test_build_stored_value_card_summary_snapshot_capture_admission_bundle_marks_snapshot_ready() -> None:
    bundle = build_stored_value_card_summary_snapshot_capture_admission_bundle(
        stored_value_card_summary_snapshot_evidence=_card_summary_evidence(),
        baseline_payload=_card_payload(),
        baseline_request_payload={
            "menuid": "E004004004",
            "gridid": "E004004004_main",
            "parameter": {"BeginDate": "2025-03-01", "EndDate": "2026-04-01", "Search": ""},
        },
    )

    detail = bundle["stored_value_card_summary_snapshot"]
    assert detail["capture_admission_ready"] is True
    assert detail["capture_route_name"] == STORED_VALUE_CARD_SUMMARY_SNAPSHOT_RECORDS_ENDPOINT
    assert detail["route_kind"] == STORED_VALUE_SUMMARY_SNAPSHOT_ROUTE_KIND


def test_persist_stored_value_card_summary_snapshot_capture_admission_bundle_writes_raw_and_snapshot_routes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(
        source_name="stored-value-card-summary-snapshot-capture-admission-test",
        capture_batch_id="stored-value-card-summary-snapshot-admit-001",
    )

    bundle = persist_stored_value_card_summary_snapshot_capture_admission_bundle(
        capture_batch_id=capture_batch_id,
        stored_value_card_summary_snapshot_evidence=_card_summary_evidence(),
        baseline_payload=_card_payload(),
        baseline_request_payload={
            "menuid": "E004004004",
            "gridid": "E004004004_main",
            "parameter": {"BeginDate": "2025-03-01", "EndDate": "2026-04-01", "Search": ""},
        },
        source_endpoint="yeusoft.report.stored_value_card_summary",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["stored_value_card_summary_snapshot"]["capture_admission_ready"] is True
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.report.stored_value_card_summary",
        STORED_VALUE_CARD_SUMMARY_SNAPSHOT_RECORDS_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", STORED_VALUE_SUMMARY_SNAPSHOT_ROUTE_KIND]


def test_build_stored_value_by_store_snapshot_capture_admission_bundle_marks_snapshot_ready() -> None:
    bundle = build_stored_value_by_store_snapshot_capture_admission_bundle(
        stored_value_by_store_snapshot_evidence=_by_store_evidence(),
        baseline_payload=_by_store_payload(),
        baseline_request_payload={
            "menuid": "E004004003",
            "gridid": "E004004003_main",
            "parameter": {"BeginDate": "2025-03-01", "EndDate": "2026-04-01"},
        },
    )

    detail = bundle["stored_value_by_store_snapshot"]
    assert detail["capture_admission_ready"] is True
    assert detail["capture_route_name"] == STORED_VALUE_BY_STORE_SNAPSHOT_RECORDS_ENDPOINT
    assert detail["route_kind"] == STORED_VALUE_SUMMARY_SNAPSHOT_ROUTE_KIND


def test_persist_stored_value_by_store_snapshot_capture_admission_bundle_writes_raw_and_snapshot_routes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(
        source_name="stored-value-by-store-snapshot-capture-admission-test",
        capture_batch_id="stored-value-by-store-snapshot-admit-001",
    )

    bundle = persist_stored_value_by_store_snapshot_capture_admission_bundle(
        capture_batch_id=capture_batch_id,
        stored_value_by_store_snapshot_evidence=_by_store_evidence(),
        baseline_payload=_by_store_payload(),
        baseline_request_payload={
            "menuid": "E004004003",
            "gridid": "E004004003_main",
            "parameter": {"BeginDate": "2025-03-01", "EndDate": "2026-04-01"},
        },
        source_endpoint="yeusoft.report.stored_value_by_store",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["stored_value_by_store_snapshot"]["capture_admission_ready"] is True
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.report.stored_value_by_store",
        STORED_VALUE_BY_STORE_SNAPSHOT_RECORDS_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", STORED_VALUE_SUMMARY_SNAPSHOT_ROUTE_KIND]
