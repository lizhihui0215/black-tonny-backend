from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.core.config import clear_settings_cache
from app.db.base import capture_endpoint_payloads
from app.db.engine import clear_engine_caches
from app.services.receipt_confirmation_capture_admission_service import (
    RECEIPT_CONFIRMATION_DOCUMENTS_ENDPOINT,
    RECEIPT_CONFIRMATION_DOCUMENTS_ROUTE_KIND,
    build_receipt_confirmation_capture_admission_bundle,
    build_receipt_confirmation_capture_research_bundle,
    persist_receipt_confirmation_capture_admission_bundle,
    persist_receipt_confirmation_capture_research_bundle,
)


def _configure_test_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CAPTURE_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'capture.db'}")
    monkeypatch.setenv("SERVING_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'serving.db'}")
    monkeypatch.setenv("PAYLOAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "sample"))
    clear_settings_cache()
    clear_engine_caches()


def _receipt_confirmation_evidence() -> dict[str, object]:
    return {
        "receipt_confirmation": {
            "capture_parameter_plan": {
                "baseline_payload": {},
                "page_seed_values": ["page=1,pagesize=20", "page=2,pagesize=20"],
                "page_size_seed_values": ["page=1,pagesize=20", "page=1,pagesize=5000"],
                "time_seed_values": ["time=20260323", "time=''"],
                "search_seed_values": ["__no_match__", "search=PFD-A019-014903"],
                "page_mode": "single_request_same_dataset_verified",
                "time_mode": "keep_default_empty_payload",
                "search_mode": "ignored_for_primary_list",
                "secondary_actions_pending": ["单据确认", "物流信息", "扫描校验"],
            },
            "capture_admission_ready": True,
            "blocking_issues": [],
            "secondary_route_blocking_issues": [
                "单据确认动作链仍依赖页面选中行或隐藏动作链",
                "物流信息动作链仍依赖页面选中行或隐藏动作链",
                "扫描校验动作链仍待识别",
            ],
        }
    }


def test_build_receipt_confirmation_capture_research_bundle_keeps_research_only_route():
    bundle = build_receipt_confirmation_capture_research_bundle(
        receipt_confirmation_evidence=_receipt_confirmation_evidence()
    )

    detail = bundle["receipt_confirmation"]
    assert detail["capture_route_name"] == RECEIPT_CONFIRMATION_DOCUMENTS_ENDPOINT
    assert detail["capture_role"] == "mainline_fact"
    assert detail["route_kind"] == "raw"
    assert detail["capture_admission_ready"] is True
    assert detail["research_only"] is True
    assert detail["capture_parameter_plan"]["page_mode"] == "single_request_same_dataset_verified"


def test_persist_receipt_confirmation_capture_research_bundle_writes_raw_and_route(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(
        source_name="receipt-confirmation-capture-research",
        capture_batch_id="receipt-confirmation-001",
    )

    bundle = persist_receipt_confirmation_capture_research_bundle(
        capture_batch_id=capture_batch_id,
        receipt_confirmation_evidence=_receipt_confirmation_evidence(),
        baseline_payload={"Data": [{"DocNo": "PFD-A019-014903"}, {"DocNo": "PFD-A019-014931"}]},
        baseline_request_payload={},
        source_endpoint="yeusoft.docs.receipt_confirmation_list",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["receipt_confirmation"]["research_only"] is True
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.docs.receipt_confirmation_list",
        RECEIPT_CONFIRMATION_DOCUMENTS_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", "raw"]


def test_build_receipt_confirmation_capture_admission_bundle_marks_document_route():
    bundle = build_receipt_confirmation_capture_admission_bundle(
        receipt_confirmation_evidence=_receipt_confirmation_evidence(),
        baseline_payload={"Data": [{"DocNo": "PFD-A019-014903"}, {"DocNo": "PFD-A019-014931"}]},
        baseline_request_payload={},
    )

    detail = bundle["receipt_confirmation"]
    assert detail["route_kind"] == RECEIPT_CONFIRMATION_DOCUMENTS_ROUTE_KIND
    assert detail["capture_admission_ready"] is True
    assert detail["capture_page_summary"]["observed_total_rows"] == 2
    assert detail["secondary_route_blocking_issues"] == [
        "单据确认动作链仍依赖页面选中行或隐藏动作链",
        "物流信息动作链仍依赖页面选中行或隐藏动作链",
        "扫描校验动作链仍待识别",
    ]


def test_persist_receipt_confirmation_capture_admission_bundle_writes_document_route(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(
        source_name="receipt-confirmation-capture-admission",
        capture_batch_id="receipt-confirmation-admission-001",
    )

    bundle = persist_receipt_confirmation_capture_admission_bundle(
        capture_batch_id=capture_batch_id,
        receipt_confirmation_evidence=_receipt_confirmation_evidence(),
        baseline_payload={"Data": [{"DocNo": "PFD-A019-014903"}, {"DocNo": "PFD-A019-014931"}]},
        baseline_request_payload={},
        source_endpoint="yeusoft.docs.receipt_confirmation_list",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["receipt_confirmation"]["research_only"] is False
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.docs.receipt_confirmation_list",
        RECEIPT_CONFIRMATION_DOCUMENTS_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", RECEIPT_CONFIRMATION_DOCUMENTS_ROUTE_KIND]
