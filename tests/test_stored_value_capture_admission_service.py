from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.core.config import clear_settings_cache
from app.db.base import capture_endpoint_payloads
from app.db.engine import clear_engine_caches
from app.services.stored_value_capture_admission_service import (
    STORED_VALUE_CARD_DETAIL_ENDPOINT,
    STORED_VALUE_CARD_DETAIL_ROUTE_KIND,
    build_stored_value_capture_admission_bundle,
    build_stored_value_capture_research_bundle,
    persist_stored_value_capture_admission_bundle,
    persist_stored_value_capture_research_bundle,
)


def _configure_test_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CAPTURE_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'capture.db'}")
    monkeypatch.setenv("SERVING_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'serving.db'}")
    monkeypatch.setenv("PAYLOAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "sample"))
    clear_settings_cache()
    clear_engine_caches()


def _stored_value_evidence() -> dict[str, object]:
    return {
        "stored_value_detail": {
            "capture_admission_ready": True,
            "blocking_issues": [],
            "capture_parameter_plan": {
                "default_BeginDate": "20250301",
                "default_EndDate": "20260401",
                "default_Search": "",
                "search_mode": "vip_card_only_filter",
                "page_mode": "single_request_half_open_date_verified",
            },
            "date_partition_verification": {
                "partition_mode": "half_open_end_date",
                "partition_union_matches_baseline": True,
            },
            "search_behavior": {
                "supported_search_groups": ["vip_card_id"],
            },
        }
    }


def _baseline_payload() -> dict[str, object]:
    return {
        "errcode": "1000",
        "retdata": {
            "ColumnsList": ["HappenNo", "VipCardId", "EndMoney"],
            "Data": [["DOC-1", "CARD-1", 2000.0]],
        },
    }


def test_build_stored_value_capture_research_bundle_preserves_research_route_shape() -> None:
    bundle = build_stored_value_capture_research_bundle(stored_value_evidence=_stored_value_evidence())

    detail = bundle["stored_value_detail"]
    assert detail["capture_route_name"] == STORED_VALUE_CARD_DETAIL_ENDPOINT
    assert detail["capture_role"] == "mainline_fact"
    assert detail["route_kind"] == "raw"
    assert detail["capture_admission_ready"] is True
    assert detail["research_only"] is True


def test_persist_stored_value_capture_research_bundle_writes_raw_and_route_payloads(monkeypatch, tmp_path: Path) -> None:
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(
        source_name="stored-value-capture-research-test",
        capture_batch_id="stored-value-cap-001",
    )

    bundle = persist_stored_value_capture_research_bundle(
        capture_batch_id=capture_batch_id,
        stored_value_evidence=_stored_value_evidence(),
        baseline_payload=_baseline_payload(),
        baseline_request_payload={"parameter": {"BeginDate": "20250301", "EndDate": "20260401", "Search": ""}},
        source_endpoint="yeusoft.report.stored_value_card_detail",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["stored_value_detail"]["research_only"] is True
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.report.stored_value_card_detail",
        STORED_VALUE_CARD_DETAIL_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", "raw"]


def test_build_stored_value_capture_admission_bundle_marks_single_request_complete() -> None:
    bundle = build_stored_value_capture_admission_bundle(
        stored_value_evidence=_stored_value_evidence(),
        baseline_payload=_baseline_payload(),
        baseline_request_payload={"parameter": {"BeginDate": "20250301", "EndDate": "20260401", "Search": ""}},
    )

    detail = bundle["stored_value_detail"]
    assert detail["capture_admission_ready"] is True
    assert detail["route_kind"] == STORED_VALUE_CARD_DETAIL_ROUTE_KIND
    assert detail["capture_page_summary"]["observed_total_rows"] == 1
    assert detail["capture_page_summary"]["capture_complete"] is True
    assert detail["capture_page_summary"]["date_partition_verified"] is True
    assert detail["capture_page_summary"]["supported_search_groups"] == ["vip_card_id"]


def test_persist_stored_value_capture_admission_bundle_writes_raw_and_detail_routes(monkeypatch, tmp_path: Path) -> None:
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(
        source_name="stored-value-capture-admission-test",
        capture_batch_id="stored-value-admit-001",
    )

    bundle = persist_stored_value_capture_admission_bundle(
        capture_batch_id=capture_batch_id,
        stored_value_evidence=_stored_value_evidence(),
        baseline_payload=_baseline_payload(),
        baseline_request_payload={"parameter": {"BeginDate": "20250301", "EndDate": "20260401", "Search": ""}},
        source_endpoint="yeusoft.report.stored_value_card_detail",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["stored_value_detail"]["capture_admission_ready"] is True
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.report.stored_value_card_detail",
        STORED_VALUE_CARD_DETAIL_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", STORED_VALUE_CARD_DETAIL_ROUTE_KIND]
