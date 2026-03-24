from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.core.config import clear_settings_cache
from app.db.base import capture_endpoint_payloads
from app.db.engine import clear_engine_caches
from app.services.store_stocktaking_secondary_capture_service import (
    STORE_STOCKTAKING_DIFF_RECORDS_ENDPOINT,
    STORE_STOCKTAKING_DIFF_RECORDS_ROUTE_KIND,
    build_store_stocktaking_diff_capture_research_bundle,
    persist_store_stocktaking_diff_capture_research_bundle,
)


def _configure_test_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CAPTURE_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'capture.db'}")
    monkeypatch.setenv("SERVING_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'serving.db'}")
    monkeypatch.setenv("PAYLOAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "sample"))
    clear_settings_cache()
    clear_engine_caches()


def _ui_probe_payload() -> dict[str, object]:
    return {
        "component_method_probes": [
            {
                "key": "component_method_getDiffData",
                "local_state_after": {
                    "snapshot": {
                        "showDiffPage": False,
                        "orderDiffData": {
                            "type": "array",
                            "length": 2,
                            "full_rows": [
                                {"PdID": "PD00000810", "SpeNum": "SKU-1", "LossMoney": "10.00"},
                                {"PdID": "PD00000810", "SpeNum": "SKU-2", "LossMoney": "5.00"},
                            ],
                        },
                        "orderDiffHJData": {
                            "type": "array",
                            "length": 1,
                            "full_rows": [{"SpeNum": "合计", "LossMoney": "15.00"}],
                        },
                        "selectItem": {"keys": ["PdID", "SpeNum"]},
                    }
                },
            }
        ]
    }


def test_build_store_stocktaking_diff_capture_research_bundle_extracts_full_rows() -> None:
    bundle = build_store_stocktaking_diff_capture_research_bundle(ui_probe_payload=_ui_probe_payload())

    detail = bundle["store_stocktaking_diff"]
    assert detail["capture_route_name"] == STORE_STOCKTAKING_DIFF_RECORDS_ENDPOINT
    assert detail["route_kind"] == STORE_STOCKTAKING_DIFF_RECORDS_ROUTE_KIND
    assert detail["research_only"] is True
    assert detail["payload"]["orderDiffData"][0]["PdID"] == "PD00000810"
    assert detail["diff_summary"]["order_diff_rows"] == 2
    assert detail["diff_summary"]["order_diff_summary_rows"] == 1


def test_persist_store_stocktaking_diff_capture_research_bundle_writes_raw_and_diff_route(monkeypatch, tmp_path: Path) -> None:
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(
        source_name="store-stocktaking-diff-capture-research",
        capture_batch_id="store-stocktaking-diff-001",
    )

    bundle = persist_store_stocktaking_diff_capture_research_bundle(
        capture_batch_id=capture_batch_id,
        ui_probe_payload=_ui_probe_payload(),
        source_endpoint="yeusoft.ui.store_stocktaking_diff_state",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["store_stocktaking_diff"]["research_only"] is True
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.ui.store_stocktaking_diff_state",
        STORE_STOCKTAKING_DIFF_RECORDS_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", STORE_STOCKTAKING_DIFF_RECORDS_ROUTE_KIND]
