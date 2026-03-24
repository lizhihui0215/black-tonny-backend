from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.core.config import clear_settings_cache
from app.db.base import capture_endpoint_payloads
from app.db.engine import clear_engine_caches
from app.services.member_analysis_snapshot_capture_admission_service import (
    MEMBER_ANALYSIS_SNAPSHOT_RECORDS_ENDPOINT,
    MEMBER_ANALYSIS_SNAPSHOT_ROUTE_KIND,
    build_member_analysis_snapshot_capture_admission_bundle,
    persist_member_analysis_snapshot_capture_admission_bundle,
)


def _configure_test_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CAPTURE_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'capture.db'}")
    monkeypatch.setenv("SERVING_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'serving.db'}")
    monkeypatch.setenv("PAYLOAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "sample"))
    clear_settings_cache()
    clear_engine_caches()


def _member_analysis_snapshot_evidence() -> dict[str, object]:
    return {
        "member_analysis_snapshot": {
            "capture_admission_ready": True,
            "blocking_issues": [],
            "capture_parameter_plan": {
                "default_salebdate": "20250301",
                "default_saleedate": "20250401",
                "default_tag": "",
                "default_type": "",
                "default_page": 0,
                "default_pagesize": 0,
                "page_mode": "page_zero_full_fetch",
                "observed_total_rows": 25,
            },
            "capture_page_summary": {
                "request_payload": {"salebdate": "20250301", "saleedate": "20250401", "page": 0, "pagesize": 0, "tag": "", "type": ""},
                "observed_total_rows": 25,
                "capture_complete": True,
            },
        }
    }


def _baseline_payload() -> dict[str, object]:
    return {
        "errcode": "1000",
        "retdata": [
            {"VipCardID": "V001", "SaleMoney": 299.0},
            {"VipCardID": "V002", "SaleMoney": 199.0},
        ],
    }


def test_build_member_analysis_snapshot_capture_admission_bundle_marks_snapshot_ready() -> None:
    bundle = build_member_analysis_snapshot_capture_admission_bundle(
        member_analysis_snapshot_evidence=_member_analysis_snapshot_evidence(),
        baseline_payload=_baseline_payload(),
        baseline_request_payload={"salebdate": "20250301", "saleedate": "20250401", "page": 0, "pagesize": 0, "tag": "", "type": ""},
    )

    detail = bundle["member_analysis_snapshot"]
    assert detail["capture_admission_ready"] is True
    assert detail["capture_route_name"] == MEMBER_ANALYSIS_SNAPSHOT_RECORDS_ENDPOINT
    assert detail["route_kind"] == MEMBER_ANALYSIS_SNAPSHOT_ROUTE_KIND
    assert detail["capture_page_summary"]["capture_complete"] is True


def test_persist_member_analysis_snapshot_capture_admission_bundle_writes_raw_and_snapshot_routes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.capture.batch_lifecycle import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(
        source_name="member-analysis-snapshot-capture-admission-test",
        capture_batch_id="member-analysis-snapshot-admit-001",
    )

    bundle = persist_member_analysis_snapshot_capture_admission_bundle(
        capture_batch_id=capture_batch_id,
        member_analysis_snapshot_evidence=_member_analysis_snapshot_evidence(),
        baseline_payload=_baseline_payload(),
        baseline_request_payload={"salebdate": "20250301", "saleedate": "20250401", "page": 0, "pagesize": 0, "tag": "", "type": ""},
        source_endpoint="yeusoft.report.member_analysis_snapshot",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["member_analysis_snapshot"]["capture_admission_ready"] is True
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.report.member_analysis_snapshot",
        MEMBER_ANALYSIS_SNAPSHOT_RECORDS_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", MEMBER_ANALYSIS_SNAPSHOT_ROUTE_KIND]
