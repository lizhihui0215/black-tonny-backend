from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.core.config import clear_settings_cache
from app.db.base import capture_endpoint_payloads
from app.db.engine import clear_engine_caches
from app.services.member_capture_admission_service import (
    MEMBER_PROFILE_RECORDS_ENDPOINT,
    build_member_capture_research_bundle,
    persist_member_capture_research_bundle,
)


def _configure_test_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CAPTURE_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'capture.db'}")
    monkeypatch.setenv("SERVING_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'serving.db'}")
    monkeypatch.setenv("PAYLOAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "sample"))
    clear_settings_cache()
    clear_engine_caches()


def _member_evidence() -> dict[str, object]:
    return {
        "member_center": {
            "capture_admission_ready": False,
            "blocking_issues": [
                "condition 语义仍待确认",
                "是否存在服务端上限仍待确认",
            ],
            "parameter_semantics": {
                "VolumeNumber": {
                    "variants": [{"value": "1"}, {"value": "2"}, {"value": "10"}],
                }
            },
            "search_behavior": {
                "exact_match_values": ["CARD-1"],
            },
        }
    }


def _baseline_payload() -> dict[str, object]:
    return {
        "errcode": "0",
        "retdata": {
            "DataCount": 2,
            "Data": [
                {"VipCardID": "CARD-1", "VipCode": "VIP001", "MobliePhone": "13800000001"},
                {"VipCardID": "CARD-2", "VipCode": "VIP002", "MobliePhone": "13800000002"},
            ],
        },
    }


def test_build_member_capture_research_bundle_keeps_blocked_research_route() -> None:
    bundle = build_member_capture_research_bundle(member_evidence=_member_evidence())

    member_center = bundle["member_center"]
    assert member_center["capture_route_name"] == MEMBER_PROFILE_RECORDS_ENDPOINT
    assert member_center["capture_role"] == "mainline_fact"
    assert member_center["route_kind"] == "raw"
    assert member_center["capture_admission_ready"] is False
    assert member_center["research_only"] is True
    assert member_center["capture_parameter_plan"]["search_mode"] == "global_filter_when_condition_empty"
    assert member_center["capture_parameter_plan"]["volume_examples"] == ["1", "2", "10"]


def test_persist_member_capture_research_bundle_writes_raw_and_route_payloads(monkeypatch, tmp_path: Path) -> None:
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(source_name="member-capture-research-test", capture_batch_id="member-cap-001")

    bundle = persist_member_capture_research_bundle(
        capture_batch_id=capture_batch_id,
        member_evidence=_member_evidence(),
        baseline_payload=_baseline_payload(),
        baseline_request_payload={"condition": "", "searchval": "", "VolumeNumber": ""},
        source_endpoint="yeusoft.report.vip_center",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["member_center"]["research_only"] is True
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.report.vip_center",
        MEMBER_PROFILE_RECORDS_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", "raw"]
