from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.core.config import clear_settings_cache
from app.db.base import capture_endpoint_payloads
from app.db.engine import clear_engine_caches
from app.services.product_capture_admission_service import (
    PRODUCT_MASTER_RECORDS_ENDPOINT,
    PRODUCT_MASTER_ROUTE_KIND,
    build_product_capture_admission_bundle,
    build_product_capture_research_bundle,
    persist_product_capture_admission_bundle,
    persist_product_capture_research_bundle,
)


def _configure_test_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CAPTURE_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'capture.db'}")
    monkeypatch.setenv("SERVING_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'serving.db'}")
    monkeypatch.setenv("PAYLOAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "sample"))
    clear_settings_cache()
    clear_engine_caches()


def _product_page_record() -> dict[str, object]:
    return {
        "payload_hints": {
            "org_fields": ["spenum", "warecause"],
            "pagination_fields": ["page", "pagesize"],
        },
        "endpoint_summaries": [{"endpoint": "SelWareList", "max_row_count": 60}],
    }


def _baseline_payload() -> dict[str, object]:
    return {
        "errcode": "0",
        "retdata": {
            "DataCount": 2,
            "Data": [
                {"spenum": "TMX1B90549A", "spename": "少女文胸", "retailprice": 89.0},
                {"spenum": "TMX1B90550A", "spename": "少女文胸", "retailprice": 69.0},
            ],
        },
    }


def _product_evidence() -> dict[str, object]:
    return {
        "product_list": {
            "capture_admission_ready": True,
            "blocking_issues": [],
            "capture_parameter_plan": {
                "default_spenum": "",
                "default_warecause": "",
                "baseline_page": 1,
                "recommended_pagesize": 5000,
                "page_mode": "sequential_pagination",
                "full_capture_with_empty_warecause": True,
            },
        }
    }


def test_build_product_capture_research_bundle_keeps_blocked_route() -> None:
    bundle = build_product_capture_research_bundle(
        product_page_record=_product_page_record(),
        blocking_issues=["尚未完成单变量探测", "尚未完成 HTTP 回证"],
    )

    product_list = bundle["product_list"]
    assert product_list["capture_route_name"] == PRODUCT_MASTER_RECORDS_ENDPOINT
    assert product_list["capture_role"] == "mainline_fact"
    assert product_list["route_kind"] == "raw"
    assert product_list["capture_parameter_plan"]["baseline_pagesize"] == 60
    assert product_list["capture_parameter_plan"]["page_mode"] == "sequential_pagination"
    assert product_list["research_only"] is True


def test_persist_product_capture_research_bundle_writes_raw_and_route_payloads(monkeypatch, tmp_path: Path) -> None:
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(source_name="product-capture-research-test", capture_batch_id="product-cap-001")

    bundle = persist_product_capture_research_bundle(
        capture_batch_id=capture_batch_id,
        product_page_record=_product_page_record(),
        blocking_issues=["尚未完成单变量探测", "尚未完成 HTTP 回证"],
        baseline_payload=_baseline_payload(),
        baseline_request_payload={"spenum": "", "warecause": "", "page": 1, "pagesize": 60},
        source_endpoint="yeusoft.master.product_list",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["product_list"]["research_only"] is True
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.master.product_list",
        PRODUCT_MASTER_RECORDS_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", "raw"]


def test_build_product_capture_admission_bundle_marks_complete_when_pages_cover_declared_total() -> None:
    bundle = build_product_capture_admission_bundle(
        product_evidence=_product_evidence(),
        page_payloads={
            1: {
                "retdata": [
                    {
                        "Count": "5",
                        "Data": [{"SpeNum": "A001"}, {"SpeNum": "A002"}],
                    }
                ]
            },
            2: {
                "retdata": [
                    {
                        "Count": "5",
                        "Data": [{"SpeNum": "A003"}, {"SpeNum": "A004"}],
                    }
                ]
            },
            3: {
                "retdata": [
                    {
                        "Count": "5",
                        "Data": [{"SpeNum": "A005"}],
                    }
                ]
            },
        },
        page_request_payloads={
            1: {"page": 1, "pagesize": 5000},
            2: {"page": 2, "pagesize": 5000},
            3: {"page": 3, "pagesize": 5000},
        },
    )

    product_list = bundle["product_list"]
    assert product_list["capture_admission_ready"] is True
    assert product_list["route_kind"] == PRODUCT_MASTER_ROUTE_KIND
    assert product_list["capture_page_summary"]["declared_total_count"] == 5
    assert product_list["capture_page_summary"]["observed_total_rows"] == 5
    assert product_list["capture_page_summary"]["capture_complete"] is True


def test_persist_product_capture_admission_bundle_writes_raw_and_master_routes(monkeypatch, tmp_path: Path) -> None:
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(source_name="product-admission-test", capture_batch_id="product-admit-001")

    bundle = persist_product_capture_admission_bundle(
        capture_batch_id=capture_batch_id,
        product_evidence=_product_evidence(),
        page_payloads={
            1: {
                "retdata": [
                    {
                        "Count": "3",
                        "Data": [{"SpeNum": "A001"}, {"SpeNum": "A002"}],
                    }
                ]
            },
            2: {
                "retdata": [
                    {
                        "Count": "3",
                        "Data": [{"SpeNum": "A003"}],
                    }
                ]
            },
        },
        page_request_payloads={
            1: {"page": 1, "pagesize": 5000},
            2: {"page": 2, "pagesize": 5000},
        },
        source_endpoint="yeusoft.master.product_list",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["product_list"]["capture_admission_ready"] is True
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.master.product_list",
        PRODUCT_MASTER_RECORDS_ENDPOINT,
        "yeusoft.master.product_list",
        PRODUCT_MASTER_RECORDS_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", PRODUCT_MASTER_ROUTE_KIND, "raw", PRODUCT_MASTER_ROUTE_KIND]
