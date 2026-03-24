from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.core.config import clear_settings_cache
from app.db.base import capture_endpoint_payloads
from app.db.engine import clear_engine_caches
from app.services.store_stocktaking_capture_admission_service import (
    STORE_STOCKTAKING_DOCUMENTS_ENDPOINT,
    STORE_STOCKTAKING_DOCUMENTS_ROUTE_KIND,
    build_store_stocktaking_capture_admission_bundle,
    build_store_stocktaking_capture_research_bundle,
    persist_store_stocktaking_capture_admission_bundle,
    persist_store_stocktaking_capture_research_bundle,
)


def _configure_test_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CAPTURE_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'capture.db'}")
    monkeypatch.setenv("SERVING_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'serving.db'}")
    monkeypatch.setenv("PAYLOAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "sample"))
    clear_settings_cache()
    clear_engine_caches()


def _stocktaking_evidence() -> dict[str, object]:
    return {
        "store_stocktaking": {
            "capture_parameter_plan": {
                "baseline_payload": {
                    "edate": "20260323",
                    "bdate": "20260316",
                    "deptcode": "",
                    "stat": "A",
                    "menuid": "E003002001",
                },
                "stat_seed_values": ["stat=A", "stat=0", "stat=1"],
                "primary_stat_values": ["A", "1"],
                "equivalent_stat_values": ["stat=1"],
                "excluded_stat_values": ["stat=0"],
                "date_seed_values": ["20260316-20260323", "20260323-20260323"],
                "page_mode": "no_pagination_field_observed",
                "date_window_mode": "fixed_bdate_edate_window",
                "secondary_actions_pending": ["查看明细", "统计损溢", "条码记录"],
            },
            "capture_admission_ready": True,
            "blocking_issues": [],
            "secondary_route_blocking_issues": [
                "查看明细二级接口仍待识别",
                "统计损溢二级接口仍待识别",
                "条码记录二级接口仍待识别",
            ],
        }
    }


def test_build_store_stocktaking_capture_research_bundle_keeps_research_only_route():
    bundle = build_store_stocktaking_capture_research_bundle(stocktaking_evidence=_stocktaking_evidence())

    detail = bundle["store_stocktaking"]
    assert detail["capture_route_name"] == STORE_STOCKTAKING_DOCUMENTS_ENDPOINT
    assert detail["capture_role"] == "mainline_fact"
    assert detail["route_kind"] == "raw"
    assert detail["capture_admission_ready"] is True
    assert detail["research_only"] is True
    assert detail["capture_parameter_plan"]["baseline_payload"]["menuid"] == "E003002001"


def test_persist_store_stocktaking_capture_research_bundle_writes_raw_and_route(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(
        source_name="store-stocktaking-capture-research",
        capture_batch_id="store-stocktaking-001",
    )

    bundle = persist_store_stocktaking_capture_research_bundle(
        capture_batch_id=capture_batch_id,
        stocktaking_evidence=_stocktaking_evidence(),
        baseline_payload={"Data": {"DataCount": 2, "Data": [{"PdID": "PD0001"}, {"PdID": "PD0002"}]}},
        baseline_request_payload={
            "edate": "20260323",
            "bdate": "20260316",
            "deptcode": "",
            "stat": "A",
            "menuid": "E003002001",
        },
        source_endpoint="yeusoft.docs.store_stocktaking_list",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["store_stocktaking"]["research_only"] is True
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.docs.store_stocktaking_list",
        STORE_STOCKTAKING_DOCUMENTS_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", "raw"]


def test_build_store_stocktaking_capture_admission_bundle_marks_document_route():
    bundle = build_store_stocktaking_capture_admission_bundle(
        stocktaking_evidence=_stocktaking_evidence(),
        baseline_payload={"Data": {"DataCount": 2, "Data": [{"PdID": "PD0001"}, {"PdID": "PD0002"}]}},
        baseline_request_payload={
            "edate": "20260323",
            "bdate": "20260316",
            "deptcode": "",
            "stat": "A",
            "menuid": "E003002001",
        },
    )

    detail = bundle["store_stocktaking"]
    assert detail["route_kind"] == STORE_STOCKTAKING_DOCUMENTS_ROUTE_KIND
    assert detail["capture_admission_ready"] is True
    assert detail["capture_page_summary"]["observed_total_rows"] == 2
    assert detail["secondary_route_blocking_issues"] == [
        "查看明细二级接口仍待识别",
        "统计损溢二级接口仍待识别",
        "条码记录二级接口仍待识别",
    ]


def test_persist_store_stocktaking_capture_admission_bundle_writes_document_route(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(
        source_name="store-stocktaking-capture-admission",
        capture_batch_id="store-stocktaking-admission-001",
    )

    bundle = persist_store_stocktaking_capture_admission_bundle(
        capture_batch_id=capture_batch_id,
        stocktaking_evidence=_stocktaking_evidence(),
        baseline_payload={"Data": {"DataCount": 2, "Data": [{"PdID": "PD0001"}, {"PdID": "PD0002"}]}},
        baseline_request_payload={
            "edate": "20260323",
            "bdate": "20260316",
            "deptcode": "",
            "stat": "A",
            "menuid": "E003002001",
        },
        source_endpoint="yeusoft.docs.store_stocktaking_list",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["store_stocktaking"]["research_only"] is False
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.docs.store_stocktaking_list",
        STORE_STOCKTAKING_DOCUMENTS_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", STORE_STOCKTAKING_DOCUMENTS_ROUTE_KIND]
