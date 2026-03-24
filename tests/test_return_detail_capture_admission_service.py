from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.core.config import clear_settings_cache
from app.db.base import capture_endpoint_payloads
from app.db.engine import clear_engine_caches
from app.services.return_detail_capture_admission_service import (
    RETURN_DOCUMENT_LINES_ENDPOINT,
    RETURN_DOCUMENT_LINES_ROUTE_KIND,
    build_return_detail_capture_research_bundle,
    persist_return_detail_capture_research_bundle,
)


def _configure_test_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CAPTURE_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'capture.db'}")
    monkeypatch.setenv("SERVING_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'serving.db'}")
    monkeypatch.setenv("PAYLOAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "sample"))
    clear_settings_cache()
    clear_engine_caches()


def _return_detail_evidence() -> dict[str, object]:
    return {
        "return_detail": {
            "capture_parameter_plan": {
                "baseline_payload": {
                    "menuid": "E004003004",
                    "gridid": "E004003004_2",
                    "warecause": "",
                    "spenum": "",
                },
                "type_seed_values": ["blank", "0", "1", "2", "3"],
                "successful_type_values": [],
                "narrow_filter_seed_values": ["TrademarkCode=01", "Years=2026"],
                "page_mode": "not_applicable_yet",
            },
            "capture_admission_ready": False,
            "blocking_issues": [
                "当前 seed type 值全部触发服务端错误",
                "服务端 SQL 截断错误仍未解除",
            ],
            "baseline": {
                "row_count": 0,
                "error_code": "4000",
                "error_message": "将截断字符串或二进制数据。",
            },
            "type_probe_summary": {
                "tested_values": ["blank", "0", "1", "2", "3"],
                "successful_values": [],
                "error_values": ["blank", "0", "1", "2", "3"],
            },
            "narrow_filter_probe_summary": {
                "tested_values": ["TrademarkCode=01", "Years=2026"],
                "successful_values": [],
                "error_values": ["TrademarkCode=01", "Years=2026"],
            },
        }
    }


def _ui_probe_payload() -> dict[str, object]:
    return {
        "_analysis_output": "tmp/capture-samples/analysis/return-detail-ui-probe-20260324-224807.json",
        "baseline": {
            "return_detail_post_data": {"menuid": "E004003004", "gridid": "E004003004_2", "type": ""},
            "page_component_state_after_query": {"component_found": True},
            "table_ref_indexeddb_after_query": {
                "database_name": "FXDATABASE",
                "database_table_name": "salesReturnDetailReport",
                "target_database": {"object_store_names": []},
            },
        },
    }


def _baseline_payload() -> dict[str, object]:
    return {
        "raw_text": '{"errcode":"4000","errmsg":"将截断字符串或二进制数据。"}',
    }


def test_build_return_detail_capture_research_bundle_keeps_blocked_route() -> None:
    bundle = build_return_detail_capture_research_bundle(
        return_detail_evidence=_return_detail_evidence(),
        ui_probe_payload=_ui_probe_payload(),
    )

    detail = bundle["return_detail"]
    assert detail["capture_route_name"] == RETURN_DOCUMENT_LINES_ENDPOINT
    assert detail["capture_role"] == "mainline_fact"
    assert detail["route_kind"] == RETURN_DOCUMENT_LINES_ROUTE_KIND
    assert detail["capture_admission_ready"] is False
    assert detail["research_only"] is True
    assert detail["baseline_analysis"]["error_code"] == "4000"
    assert detail["ui_probe_summary"]["component_found"] is True


def test_persist_return_detail_capture_research_bundle_writes_raw_and_route(monkeypatch, tmp_path: Path) -> None:
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(
        source_name="return-detail-capture-research",
        capture_batch_id="return-detail-001",
    )

    bundle = persist_return_detail_capture_research_bundle(
        capture_batch_id=capture_batch_id,
        return_detail_evidence=_return_detail_evidence(),
        baseline_payload=_baseline_payload(),
        baseline_request_payload={"menuid": "E004003004", "gridid": "E004003004_2", "warecause": "", "spenum": "", "type": ""},
        source_endpoint="yeusoft.docs.return_detail",
        account_context={"dept_code": "A0190248"},
        ui_probe_payload=_ui_probe_payload(),
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["return_detail"]["research_only"] is True
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.docs.return_detail",
        RETURN_DOCUMENT_LINES_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", RETURN_DOCUMENT_LINES_ROUTE_KIND]
