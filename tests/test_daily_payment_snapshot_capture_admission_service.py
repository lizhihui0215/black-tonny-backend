from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.core.config import clear_settings_cache
from app.db.base import capture_endpoint_payloads
from app.db.engine import clear_engine_caches
from app.services.daily_payment_snapshot_capture_admission_service import (
    DAILY_PAYMENT_SNAPSHOT_RECORDS_ENDPOINT,
    DAILY_PAYMENT_SNAPSHOT_ROUTE_KIND,
    build_daily_payment_snapshot_capture_admission_bundle,
    persist_daily_payment_snapshot_capture_admission_bundle,
)


def _configure_test_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CAPTURE_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'capture.db'}")
    monkeypatch.setenv("SERVING_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'serving.db'}")
    monkeypatch.setenv("PAYLOAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "sample"))
    clear_settings_cache()
    clear_engine_caches()


def _daily_payment_snapshot_evidence() -> dict[str, object]:
    return {
        "daily_payment_snapshot": {
            "capture_admission_ready": True,
            "blocking_issues": [],
            "capture_parameter_plan": {
                "default_menu_id": "E004006001",
                "default_search_type": "1",
                "default_search": "",
                "default_last_date": "",
                "default_begin_date": "2025-03-01",
                "default_end_date": "2026-04-01",
                "page_mode": "single_request_no_pagination_fields",
                "observed_total_rows": 2,
                "searchtype_semantics": {
                    "tested_values": ["", "1", "2"],
                    "same_dataset_values": ["", "1", "2"],
                    "different_dataset_values": [],
                    "error_values": [],
                    "same_dataset_for_tested_values": True,
                },
            },
            "capture_page_summary": {
                "request_payload": {
                    "MenuID": "E004006001",
                    "SearchType": "1",
                    "Search": "",
                    "LastDate": "",
                    "BeginDate": "2025-03-01",
                    "EndDate": "2026-04-01",
                },
                "observed_total_rows": 2,
                "capture_complete": True,
            },
        }
    }


def _baseline_payload() -> dict[str, object]:
    return {
        "Success": True,
        "Code": 200,
        "Data": {
            "Columns": ["DocNo", "Money"],
            "List": [["A001", 100.0], ["A002", 80.0]],
        },
    }


def test_build_daily_payment_snapshot_capture_admission_bundle_marks_snapshot_ready() -> None:
    bundle = build_daily_payment_snapshot_capture_admission_bundle(
        daily_payment_snapshot_evidence=_daily_payment_snapshot_evidence(),
        baseline_payload=_baseline_payload(),
        baseline_request_payload={
            "MenuID": "E004006001",
            "SearchType": "1",
            "Search": "",
            "LastDate": "",
            "BeginDate": "2025-03-01",
            "EndDate": "2026-04-01",
        },
    )

    detail = bundle["daily_payment_snapshot"]
    assert detail["capture_admission_ready"] is True
    assert detail["capture_route_name"] == DAILY_PAYMENT_SNAPSHOT_RECORDS_ENDPOINT
    assert detail["route_kind"] == DAILY_PAYMENT_SNAPSHOT_ROUTE_KIND
    assert detail["capture_page_summary"]["capture_complete"] is True


def test_persist_daily_payment_snapshot_capture_admission_bundle_writes_raw_and_snapshot_routes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(
        source_name="daily-payment-snapshot-capture-admission-test",
        capture_batch_id="daily-payment-snapshot-admit-001",
    )

    bundle = persist_daily_payment_snapshot_capture_admission_bundle(
        capture_batch_id=capture_batch_id,
        daily_payment_snapshot_evidence=_daily_payment_snapshot_evidence(),
        baseline_payload=_baseline_payload(),
        baseline_request_payload={
            "MenuID": "E004006001",
            "SearchType": "1",
            "Search": "",
            "LastDate": "",
            "BeginDate": "2025-03-01",
            "EndDate": "2026-04-01",
        },
        source_endpoint="yeusoft.report.daily_payment_snapshot",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["daily_payment_snapshot"]["capture_admission_ready"] is True
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.report.daily_payment_snapshot",
        DAILY_PAYMENT_SNAPSHOT_RECORDS_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", DAILY_PAYMENT_SNAPSHOT_ROUTE_KIND]
