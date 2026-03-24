from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.core.config import clear_settings_cache
from app.db.base import capture_endpoint_payloads
from app.db.engine import clear_engine_caches
from app.services.member_maintenance_capture_admission_service import (
    MEMBER_MAINTENANCE_RECORDS_ENDPOINT,
    MEMBER_MAINTENANCE_ROUTE_KIND,
    build_member_maintenance_capture_admission_bundle,
    build_member_maintenance_capture_research_bundle,
    persist_member_maintenance_capture_admission_bundle,
    persist_member_maintenance_capture_research_bundle,
)


def _configure_test_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CAPTURE_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'capture.db'}")
    monkeypatch.setenv("SERVING_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'serving.db'}")
    monkeypatch.setenv("PAYLOAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "sample"))
    clear_settings_cache()
    clear_engine_caches()


def _member_maintenance_evidence() -> dict[str, object]:
    return {
        "member_maintenance": {
            "capture_parameter_plan": {
                "default_search": "",
                "default_type": "",
                "baseline_page": 1,
                "baseline_pagesize": 20,
                "page_mode": "single_request_stable_empty_verified",
                "empty_dataset_confirmed": True,
            },
            "baseline": {"row_count": 0},
            "capture_admission_ready": True,
            "blocking_issues": [],
        }
    }


def _baseline_payload() -> dict[str, object]:
    return {
        "errcode": "1000",
        "errmsg": "暂无数据",
        "retdata": {"Count": "0", "Data": []},
    }


def test_build_member_maintenance_capture_research_bundle_keeps_blocked_route() -> None:
    bundle = build_member_maintenance_capture_research_bundle(
        member_maintenance_evidence=_member_maintenance_evidence()
    )

    detail = bundle["member_maintenance"]
    assert detail["capture_route_name"] == MEMBER_MAINTENANCE_RECORDS_ENDPOINT
    assert detail["capture_role"] == "mainline_fact"
    assert detail["route_kind"] == "raw"
    assert detail["capture_parameter_plan"]["baseline_pagesize"] == 20
    assert detail["research_only"] is True


def test_persist_member_maintenance_capture_research_bundle_writes_raw_and_route_payloads(monkeypatch, tmp_path: Path) -> None:
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(
        source_name="member-maintenance-capture-research-test",
        capture_batch_id="member-maint-cap-001",
    )

    bundle = persist_member_maintenance_capture_research_bundle(
        capture_batch_id=capture_batch_id,
        member_maintenance_evidence=_member_maintenance_evidence(),
        baseline_payload=_baseline_payload(),
        baseline_request_payload={
            "search": "",
            "type": "",
            "bdate": "",
            "edate": "",
            "brdate": "",
            "erdate": "",
            "page": 1,
            "pagesize": 20,
        },
        source_endpoint="yeusoft.member.member_maintenance",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["member_maintenance"]["research_only"] is True
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.member.member_maintenance",
        MEMBER_MAINTENANCE_RECORDS_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", "raw"]


def test_build_member_maintenance_capture_admission_bundle_marks_empty_dataset_complete() -> None:
    bundle = build_member_maintenance_capture_admission_bundle(
        member_maintenance_evidence=_member_maintenance_evidence(),
        baseline_payload=_baseline_payload(),
        baseline_request_payload={
            "search": "",
            "type": "",
            "bdate": "",
            "edate": "",
            "brdate": "",
            "erdate": "",
            "page": 1,
            "pagesize": 20,
        },
    )

    detail = bundle["member_maintenance"]
    assert detail["capture_admission_ready"] is True
    assert detail["route_kind"] == MEMBER_MAINTENANCE_ROUTE_KIND
    assert detail["capture_page_summary"]["observed_total_rows"] == 0
    assert detail["capture_page_summary"]["empty_dataset_confirmed"] is True


def test_persist_member_maintenance_capture_admission_bundle_writes_master_route(monkeypatch, tmp_path: Path) -> None:
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(
        source_name="member-maintenance-capture-admission-test",
        capture_batch_id="member-maint-admit-001",
    )

    bundle = persist_member_maintenance_capture_admission_bundle(
        capture_batch_id=capture_batch_id,
        member_maintenance_evidence=_member_maintenance_evidence(),
        baseline_payload=_baseline_payload(),
        baseline_request_payload={
            "search": "",
            "type": "",
            "bdate": "",
            "edate": "",
            "brdate": "",
            "erdate": "",
            "page": 1,
            "pagesize": 20,
        },
        source_endpoint="yeusoft.member.member_maintenance",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["member_maintenance"]["research_only"] is False
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.member.member_maintenance",
        MEMBER_MAINTENANCE_RECORDS_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", MEMBER_MAINTENANCE_ROUTE_KIND]
