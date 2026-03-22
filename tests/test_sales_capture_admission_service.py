from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy import select

from app.core.config import clear_settings_cache
from app.db.base import capture_endpoint_payloads
from app.db.engine import clear_engine_caches
from app.services.sales_capture_admission_service import (
    SALES_DOCUMENT_LINES_ENDPOINT,
    SALES_DOCUMENTS_HEAD_ENDPOINT,
    SALES_REVERSE_DOCUMENT_LINES_ENDPOINT,
    build_sales_capture_admission_bundle,
    persist_sales_capture_admission_bundle,
)


def _configure_test_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CAPTURE_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'capture.db'}")
    monkeypatch.setenv("SERVING_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'serving.db'}")
    monkeypatch.setenv("PAYLOAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "sample"))
    clear_settings_cache()
    clear_engine_caches()


def _document_payload() -> dict[str, object]:
    return {
        "retdata": {
            "ColumnsList": ["零售单号", "销售日期", "导购员", "会员卡号", "实收金额"],
            "Data": [
                ["S0001", "2026-03-20", "A", "VIP01", "120.00"],
                ["S0002", "2026-03-20", "B", "VIP02", "80.00"],
            ],
        }
    }


def _detail_payload() -> dict[str, object]:
    return {
        "retdata": {
            "ColumnsList": ["零售单号", "明细流水", "款号", "颜色", "尺码", "数量", "金额", "导购员"],
            "Data": [
                ["S0001", "1", "A01", "粉", "90", "1", "60.00", "A"],
                ["S0001", "2", "A02", "蓝", "100", "1", "60.00", "A"],
                ["S0002", "1", "B01", "黄", "110", "2", "80.00", "B"],
                ["R0001", "1", "A01", "粉", "90", "-1", "-60.00", "A"],
                ["RX001", "1", "B01", "黄", "110", "1", "40.00", "B"],
                ["RX001", "2", "B01", "黄", "110", "-1", "-40.00", "B"],
            ],
        }
    }


def test_build_sales_capture_admission_bundle_splits_normal_and_reverse_rows():
    bundle = build_sales_capture_admission_bundle(
        document_payload=_document_payload(),
        detail_payload=_detail_payload(),
    )

    assert bundle["head_document_uniqueness"]["head_document_uniqueness_ok"] is True
    assert bundle["normal_route_summary"]["sale_no_count"] == 2
    assert bundle["normal_route_summary"]["row_count"] == 3
    assert bundle["reverse_route_summary"]["detail_only_sale_no_count"] == 2
    assert bundle["reverse_route_summary"]["detail_only_row_count"] == 3
    assert bundle["reverse_route_summary"]["negative_only_sale_no_count"] == 1
    assert bundle["reverse_route_summary"]["mixed_sign_sale_no_count"] == 1
    assert bundle["reverse_split_ready"] is True
    assert bundle["capture_admission_ready"] is True
    assert len(bundle["route_payloads"][SALES_DOCUMENTS_HEAD_ENDPOINT]) == 2
    assert len(bundle["route_payloads"][SALES_DOCUMENT_LINES_ENDPOINT]) == 3
    assert len(bundle["route_payloads"][SALES_REVERSE_DOCUMENT_LINES_ENDPOINT]) == 3


def test_persist_sales_capture_admission_bundle_writes_route_kind(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(source_name="sales-admission-test", capture_batch_id="sales-admit-001")

    bundle = persist_sales_capture_admission_bundle(
        capture_batch_id=capture_batch_id,
        document_payload=_document_payload(),
        detail_payload=_detail_payload(),
        document_request_payload={"page": 1},
        detail_request_payload={"menuid": "E004001008", "gridid": "E004001008_2"},
        document_source_endpoint="yeusoft.report.sales_document_route",
        detail_source_endpoint="yeusoft.report.sales_list",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["capture_admission_ready"] is True
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.report.sales_document_route",
        "yeusoft.report.sales_list",
        SALES_DOCUMENTS_HEAD_ENDPOINT,
        SALES_DOCUMENT_LINES_ENDPOINT,
        SALES_REVERSE_DOCUMENT_LINES_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", "raw", "head", "line", "reverse"]


def test_init_databases_backfills_route_kind_column(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    capture_db = tmp_path / "capture.db"
    engine = create_engine(f"sqlite+pysqlite:///{capture_db}", future=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE capture_batches (
                    capture_batch_id VARCHAR(64) PRIMARY KEY,
                    batch_status VARCHAR(32) NOT NULL,
                    source_name VARCHAR(128) NOT NULL,
                    pulled_at DATETIME NULL,
                    transformed_at DATETIME NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    error_message TEXT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE capture_endpoint_payloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    capture_batch_id VARCHAR(64) NOT NULL,
                    source_endpoint VARCHAR(128) NOT NULL,
                    page_cursor VARCHAR(128) NULL,
                    page_no INTEGER NULL,
                    request_params TEXT NULL,
                    payload_json TEXT NOT NULL,
                    checksum VARCHAR(128) NOT NULL,
                    pulled_at DATETIME NOT NULL,
                    created_at DATETIME NOT NULL
                )
                """
            )
        )

    from app.db.engine import init_databases

    init_databases()

    columns = {column["name"] for column in inspect(create_engine(f"sqlite+pysqlite:///{capture_db}", future=True)).get_columns("capture_endpoint_payloads")}
    assert "route_kind" in columns
