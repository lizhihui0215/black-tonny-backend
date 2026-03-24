from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.core.config import clear_settings_cache
from app.db.base import capture_endpoint_payloads
from app.db.engine import clear_engine_caches
from app.services.product_sales_snapshot_capture_admission_service import (
    PRODUCT_SALES_SNAPSHOT_RECORDS_ENDPOINT,
    PRODUCT_SALES_SNAPSHOT_ROUTE_KIND,
    build_product_sales_snapshot_capture_admission_bundle,
    persist_product_sales_snapshot_capture_admission_bundle,
)


def _configure_test_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CAPTURE_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'capture.db'}")
    monkeypatch.setenv("SERVING_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'serving.db'}")
    monkeypatch.setenv("PAYLOAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "sample"))
    clear_settings_cache()
    clear_engine_caches()


def _product_sales_snapshot_evidence() -> dict[str, object]:
    return {
        "product_sales_snapshot": {
            "capture_admission_ready": True,
            "blocking_issues": [],
            "capture_parameter_plan": {
                "default_bdate": "20250301",
                "default_edate": "20260401",
                "default_warecause": "",
                "default_spenum": "",
                "page_mode": "single_request_declared_total_match",
                "declared_total_count": 2,
                "observed_total_rows": 2,
            },
            "capture_page_summary": {
                "request_payload": {"bdate": "20250301", "edate": "20260401", "warecause": "", "spenum": ""},
                "declared_total_count": 2,
                "observed_total_rows": 2,
                "capture_complete": True,
            },
        }
    }


def _baseline_payload() -> dict[str, object]:
    return {
        "errcode": "1000",
        "retdata": {
            "Count": 2,
            "Data": [
                {"WareCode": "W001", "SaleAmount": 3, "SaleMoney": 299.0},
                {"WareCode": "W002", "SaleAmount": 1, "SaleMoney": 99.0},
            ],
        },
    }


def test_build_product_sales_snapshot_capture_admission_bundle_marks_snapshot_ready() -> None:
    bundle = build_product_sales_snapshot_capture_admission_bundle(
        product_sales_snapshot_evidence=_product_sales_snapshot_evidence(),
        baseline_payload=_baseline_payload(),
        baseline_request_payload={"bdate": "20250301", "edate": "20260401", "warecause": "", "spenum": ""},
    )

    detail = bundle["product_sales_snapshot"]
    assert detail["capture_admission_ready"] is True
    assert detail["capture_route_name"] == PRODUCT_SALES_SNAPSHOT_RECORDS_ENDPOINT
    assert detail["route_kind"] == PRODUCT_SALES_SNAPSHOT_ROUTE_KIND
    assert detail["capture_page_summary"]["capture_complete"] is True


def test_persist_product_sales_snapshot_capture_admission_bundle_writes_raw_and_snapshot_routes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(
        source_name="product-sales-snapshot-capture-admission-test",
        capture_batch_id="product-sales-snapshot-admit-001",
    )

    bundle = persist_product_sales_snapshot_capture_admission_bundle(
        capture_batch_id=capture_batch_id,
        product_sales_snapshot_evidence=_product_sales_snapshot_evidence(),
        baseline_payload=_baseline_payload(),
        baseline_request_payload={"bdate": "20250301", "edate": "20260401", "warecause": "", "spenum": ""},
        source_endpoint="yeusoft.report.product_sales_snapshot",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["product_sales_snapshot"]["capture_admission_ready"] is True
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.report.product_sales_snapshot",
        PRODUCT_SALES_SNAPSHOT_RECORDS_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", PRODUCT_SALES_SNAPSHOT_ROUTE_KIND]
