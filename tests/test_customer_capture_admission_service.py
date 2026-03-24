from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.core.config import clear_settings_cache
from app.db.base import capture_endpoint_payloads
from app.db.engine import clear_engine_caches
from app.services.customer_capture_admission_service import (
    CUSTOMER_MASTER_RECORDS_ENDPOINT,
    CUSTOMER_MASTER_ROUTE_KIND,
    build_customer_capture_admission_bundle,
    build_customer_capture_research_bundle,
    persist_customer_capture_admission_bundle,
    persist_customer_capture_research_bundle,
)


def _configure_test_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CAPTURE_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'capture.db'}")
    monkeypatch.setenv("SERVING_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'serving.db'}")
    monkeypatch.setenv("PAYLOAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "sample"))
    clear_settings_cache()
    clear_engine_caches()


def _customer_page_record() -> dict[str, object]:
    return {
        "payload_hints": {
            "search_fields": ["deptname"],
            "pagination_fields": ["page", "pagesize"],
        },
        "endpoint_summaries": [{"endpoint": "SelDeptList", "max_row_count": 0}],
    }


def _baseline_payload() -> dict[str, object]:
    return {
        "errcode": "1000",
        "retdata": {
            "Count": "0",
            "Data": [{}],
        },
    }


def test_build_customer_capture_research_bundle_keeps_blocked_route() -> None:
    bundle = build_customer_capture_research_bundle(
        customer_page_record=_customer_page_record(),
        blocking_issues=["尚未完成单变量探测", "尚未完成 HTTP 回证", "当前账号下 baseline 为空，需确认是否长期为空"],
        baseline_row_count=0,
    )

    customer_list = bundle["customer_list"]
    assert customer_list["capture_route_name"] == CUSTOMER_MASTER_RECORDS_ENDPOINT
    assert customer_list["capture_role"] == "mainline_fact"
    assert customer_list["route_kind"] == "raw"
    assert customer_list["capture_parameter_plan"]["baseline_pagesize"] == 20
    assert customer_list["capture_parameter_plan"]["page_mode"] == "sequential_pagination"
    assert customer_list["research_only"] is True


def test_persist_customer_capture_research_bundle_writes_raw_and_route_payloads(monkeypatch, tmp_path: Path) -> None:
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(source_name="customer-capture-research-test", capture_batch_id="customer-cap-001")

    bundle = persist_customer_capture_research_bundle(
        capture_batch_id=capture_batch_id,
        customer_page_record=_customer_page_record(),
        blocking_issues=["尚未完成单变量探测", "尚未完成 HTTP 回证", "当前账号下 baseline 为空，需确认是否长期为空"],
        baseline_payload=_baseline_payload(),
        baseline_request_payload={"deptname": "", "page": 1, "pagesize": 20},
        source_endpoint="yeusoft.master.customer_list",
        account_context={"dept_code": "A0190248"},
        baseline_row_count=0,
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["customer_list"]["research_only"] is True
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.master.customer_list",
        CUSTOMER_MASTER_RECORDS_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", "raw"]


def _customer_evidence() -> dict[str, object]:
    return {
        "customer_list": {
            "capture_admission_ready": True,
            "blocking_issues": [],
            "capture_parameter_plan": {
                "default_deptname": "",
                "baseline_page": 1,
                "baseline_pagesize": 20,
                "page_mode": "single_request_stable_empty_verified",
                "empty_dataset_confirmed": True,
            },
            "baseline": {"row_count": 0},
        }
    }


def test_build_customer_capture_admission_bundle_marks_empty_dataset_complete() -> None:
    bundle = build_customer_capture_admission_bundle(
        customer_evidence=_customer_evidence(),
        baseline_payload=_baseline_payload(),
        baseline_request_payload={"deptname": "", "page": 1, "pagesize": 20},
    )

    customer_list = bundle["customer_list"]
    assert customer_list["capture_admission_ready"] is True
    assert customer_list["route_kind"] == CUSTOMER_MASTER_ROUTE_KIND
    assert customer_list["capture_page_summary"]["observed_total_rows"] == 0
    assert customer_list["capture_page_summary"]["empty_dataset_confirmed"] is True


def test_persist_customer_capture_admission_bundle_writes_master_route(monkeypatch, tmp_path: Path) -> None:
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(source_name="customer-capture-admission-test", capture_batch_id="customer-admit-001")

    bundle = persist_customer_capture_admission_bundle(
        capture_batch_id=capture_batch_id,
        customer_evidence=_customer_evidence(),
        baseline_payload=_baseline_payload(),
        baseline_request_payload={"deptname": "", "page": 1, "pagesize": 20},
        source_endpoint="yeusoft.master.customer_list",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["customer_list"]["research_only"] is False
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.master.customer_list",
        CUSTOMER_MASTER_RECORDS_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", CUSTOMER_MASTER_ROUTE_KIND]
