from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.core.config import clear_settings_cache
from app.db.base import capture_endpoint_payloads
from app.db.engine import clear_engine_caches
from app.services.inventory_capture_admission_service import (
    INVENTORY_INOUT_DOCUMENTS_ENDPOINT,
    INVENTORY_STOCK_WAIT_LINES_ENDPOINT,
    build_outin_research_sweep_summary,
    build_inventory_capture_admission_bundle,
    persist_inventory_detail_capture_admission_bundle,
    persist_outin_capture_admission_bundle,
    persist_outin_capture_research_bundle,
)


def _inventory_evidence() -> dict[str, object]:
    return {
        "inventory_detail": {
            "parameter_semantics": {
                "stockflag": {
                    "semantics": "data_subset_or_scope_switch",
                    "variants": [{"value": "0"}, {"value": "1"}, {"value": "2"}],
                },
                "page": {
                    "semantics": "same_dataset",
                },
            },
            "stockflag_equivalence": {
                "stockflag_1_equals_2": True,
            },
        },
        "outin_report": {
            "parameter_semantics": {
                "datetype": {
                    "semantics": "data_subset_or_scope_switch",
                    "variants": [{"value": "1"}, {"value": "2"}],
                },
                "type": {
                    "semantics": "data_subset_or_scope_switch",
                },
                "doctype": {
                    "semantics": "data_subset_or_scope_switch",
                },
            },
            "type_sweep_summary": {
                "recommended_distinct_values": ["已出库", "已入库", "在途"],
            },
            "doctype_sweep_summary": {
                "recommended_distinct_values": ["1", "2", "3", "7"],
                "equivalent_value_groups": [["3", "4", "5", "6"]],
            },
        },
    }


def _configure_test_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CAPTURE_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'capture.db'}")
    monkeypatch.setenv("SERVING_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'serving.db'}")
    monkeypatch.setenv("PAYLOAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "sample"))
    clear_settings_cache()
    clear_engine_caches()


def _table_payload(rows: list[list[object]]) -> dict[str, object]:
    return {
        "retdata": [
            {
                "ColumnsList": ["Sku", "Qty", "RetailPrice"],
                "Data": rows,
            }
        ]
    }


def _outin_payload_for_combo(datetype: str, type_value: str, doctype: str) -> dict[str, object]:
    columns = ["DocNo", "Qty", "Amount"]
    if doctype == "3":
        columns = ["DocNo", "Qty", "Amount", "TransitFlag"]
    row = [f"{datetype}-{type_value}-{doctype}", 1, 10]
    if doctype == "3":
        row.append("Y")
    return {
        "retdata": [
            {
                "Data": [row],
                "ColumnsList": columns,
            }
        ]
    }


def _outin_payload_for_combo_with_placeholder_doctype(datetype: str, type_value: str, doctype: str) -> dict[str, object]:
    if doctype == "3":
        return {
            "retdata": [
                {
                    "Data": [{}],
                    "ColumnsList": ["DocNo", "Qty", "Amount"],
                }
            ]
        }
    return _outin_payload_for_combo(datetype, type_value, doctype)


def test_build_inventory_capture_admission_bundle_builds_fixed_page_zero_and_minimum_sweeps():
    bundle = build_inventory_capture_admission_bundle(inventory_evidence=_inventory_evidence())

    inventory_detail = bundle["inventory_detail"]
    assert inventory_detail["capture_route_name"] == INVENTORY_STOCK_WAIT_LINES_ENDPOINT
    assert inventory_detail["recommended_stockflag_values"] == ["0", "1"]
    assert inventory_detail["stockflag_equivalent_groups"] == [["1", "2"]]
    assert inventory_detail["page_strategy"]["mode"] == "fixed_page_zero"
    assert inventory_detail["capture_parameter_plan"] == {
        "stockflag_values": ["0", "1"],
        "page_mode": "fixed_page_zero",
    }
    assert inventory_detail["capture_admission_ready"] is True
    assert inventory_detail["blocking_issues"] == []

    outin_report = bundle["outin_report"]
    assert outin_report["capture_route_name"] == INVENTORY_INOUT_DOCUMENTS_ENDPOINT
    assert outin_report["recommended_datetype_values"] == ["1", "2"]
    assert outin_report["recommended_type_values"] == ["已出库", "已入库", "在途"]
    assert outin_report["recommended_doctype_values"] == ["1", "2", "3", "7"]
    assert outin_report["doctype_equivalent_groups"] == [["3", "4", "5", "6"]]
    assert len(outin_report["recommended_minimum_sweeps"]) == 24
    assert outin_report["capture_admission_ready"] is False
    assert outin_report["blocking_issues"] == [
        "仍需验证 datetype × type × doctype 的最小组合 sweep 是否稳定覆盖单据集合。"
    ]


def test_build_inventory_capture_admission_bundle_keeps_followup_when_page_semantics_is_mixed():
    evidence = _inventory_evidence()
    inventory_detail = evidence["inventory_detail"]
    assert isinstance(inventory_detail, dict)
    inventory_detail["parameter_semantics"]["page"]["semantics"] = "mixed_by_scope"  # type: ignore[index]

    bundle = build_inventory_capture_admission_bundle(inventory_evidence=evidence)

    assert bundle["inventory_detail"]["capture_admission_ready"] is False
    assert bundle["inventory_detail"]["page_strategy"]["mode"] == "needs_followup"
    assert "仍需继续拆解前端附加参数与页面动作链" in bundle["inventory_detail"]["blocking_issues"][0]


def test_persist_inventory_detail_capture_admission_bundle_writes_raw_and_stock_routes(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(source_name="inventory-admission-test", capture_batch_id="inventory-admit-001")

    bundle = persist_inventory_detail_capture_admission_bundle(
        capture_batch_id=capture_batch_id,
        inventory_evidence=_inventory_evidence(),
        stockflag_payloads={
            "0": _table_payload([["SKU-1", 5, 100], ["SKU-2", 4, 120]]),
            "1": _table_payload([["SKU-1", 5, 100], ["SKU-3", 2, 88], ["SKU-4", 1, 66]]),
        },
        stockflag_request_payloads={
            "0": {"stockflag": "0", "page": 0},
            "1": {"stockflag": "1", "page": 0},
        },
        source_endpoint="yeusoft.report.inventory_stock_wait",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["inventory_detail"]["capture_admission_ready"] is True
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.report.inventory_stock_wait",
        INVENTORY_STOCK_WAIT_LINES_ENDPOINT,
        "yeusoft.report.inventory_stock_wait",
        INVENTORY_STOCK_WAIT_LINES_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", "stock", "raw", "stock"]


def test_persist_outin_capture_research_bundle_writes_raw_and_document_routes(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(source_name="inventory-outin-research", capture_batch_id="inventory-outin-001")

    bundle = persist_outin_capture_research_bundle(
        capture_batch_id=capture_batch_id,
        inventory_evidence=_inventory_evidence(),
        sweep_payloads=[
            {
                "datetype": "1",
                "type": "已出库",
                "doctype": "1",
                "payload": _table_payload([["DOC-1", 2, 20]]),
                "request_payload": {"datetype": "1", "type": "已出库", "doctype": "1"},
            },
            {
                "datetype": "2",
                "type": "已入库",
                "doctype": "2",
                "payload": _table_payload([["DOC-2", 1, 10]]),
                "request_payload": {"datetype": "2", "type": "已入库", "doctype": "2"},
            },
        ],
        source_endpoint="yeusoft.report.inventory_outin",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["outin_report"]["capture_admission_ready"] is False
    assert bundle["outin_report"]["research_sweep_summary"]["provided_sweep_count"] == 2
    assert bundle["outin_report"]["research_sweep_summary"]["expected_minimum_sweep_count"] == 24
    assert bundle["outin_report"]["research_sweep_summary"]["minimum_sweep_complete"] is False
    assert [row["source_endpoint"] for row in rows] == [
        "yeusoft.report.inventory_outin",
        INVENTORY_INOUT_DOCUMENTS_ENDPOINT,
        "yeusoft.report.inventory_outin",
        INVENTORY_INOUT_DOCUMENTS_ENDPOINT,
    ]
    assert [row["route_kind"] for row in rows] == ["raw", "document", "raw", "document"]


def test_build_outin_research_sweep_summary_and_bundle_marks_ready_when_minimum_sweep_is_complete():
    evidence = _inventory_evidence()
    base_bundle = build_inventory_capture_admission_bundle(inventory_evidence=evidence)
    expected_sweeps = base_bundle["outin_report"]["recommended_minimum_sweeps"]
    sweep_payloads = [
        {
            "datetype": combo["datetype"],
            "type": combo["type"],
            "doctype": combo["doctype"],
            "payload": _outin_payload_for_combo(combo["datetype"], combo["type"], combo["doctype"]),
            "request_payload": {
                "datetype": combo["datetype"],
                "type": combo["type"],
                "doctype": combo["doctype"],
            },
        }
        for combo in expected_sweeps
    ]

    sweep_summary = build_outin_research_sweep_summary(
        expected_sweeps=expected_sweeps,
        sweep_payloads=sweep_payloads,
    )
    enriched_bundle = build_inventory_capture_admission_bundle(
        inventory_evidence=evidence,
        outin_research_sweep_summary=sweep_summary,
    )

    assert sweep_summary["minimum_sweep_complete"] is True
    assert sweep_summary["doctype_schema_stable"] is True
    assert sweep_summary["provided_sweep_count"] == 24
    assert set(sweep_summary["validated_doctype_values"]) == {"1", "2", "3", "7"}
    assert enriched_bundle["outin_report"]["capture_admission_ready"] is True
    assert enriched_bundle["outin_report"]["blocking_issues"] == []
    assert enriched_bundle["outin_report"]["capture_parameter_plan"]["validated_minimum_sweep"] is True


def test_build_outin_research_sweep_summary_filters_placeholder_only_doctype():
    evidence = _inventory_evidence()
    base_bundle = build_inventory_capture_admission_bundle(inventory_evidence=evidence)
    expected_sweeps = base_bundle["outin_report"]["recommended_minimum_sweeps"]
    sweep_payloads = [
        {
            "datetype": combo["datetype"],
            "type": combo["type"],
            "doctype": combo["doctype"],
            "payload": _outin_payload_for_combo_with_placeholder_doctype(
                combo["datetype"],
                combo["type"],
                combo["doctype"],
            ),
            "request_payload": combo,
        }
        for combo in expected_sweeps
    ]

    sweep_summary = build_outin_research_sweep_summary(
        expected_sweeps=expected_sweeps,
        sweep_payloads=sweep_payloads,
    )
    enriched_bundle = build_inventory_capture_admission_bundle(
        inventory_evidence=evidence,
        outin_research_sweep_summary=sweep_summary,
    )

    assert sweep_summary["minimum_sweep_complete"] is True
    assert sweep_summary["doctype_schema_stable"] is True
    assert sweep_summary["active_doctype_values"] == ["1", "2", "7"]
    assert sweep_summary["placeholder_only_doctype_values"] == ["3"]
    assert enriched_bundle["outin_report"]["capture_admission_ready"] is True
    assert enriched_bundle["outin_report"]["recommended_doctype_values"] == ["1", "2", "7"]
    assert enriched_bundle["outin_report"]["capture_parameter_plan"]["doctype_values"] == ["1", "2", "7"]


def test_persist_outin_capture_admission_bundle_writes_only_active_doctype_routes(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, init_databases
    from app.services.batch_service import create_capture_batch

    init_databases()
    capture_batch_id = create_capture_batch(source_name="inventory-outin-admission", capture_batch_id="inventory-outin-002")

    evidence = _inventory_evidence()
    base_bundle = build_inventory_capture_admission_bundle(inventory_evidence=evidence)
    expected_sweeps = base_bundle["outin_report"]["recommended_minimum_sweeps"]
    sweep_payloads = [
        {
            "datetype": combo["datetype"],
            "type": combo["type"],
            "doctype": combo["doctype"],
            "payload": _outin_payload_for_combo_with_placeholder_doctype(
                combo["datetype"],
                combo["type"],
                combo["doctype"],
            ),
            "request_payload": combo,
        }
        for combo in expected_sweeps
    ]

    bundle = persist_outin_capture_admission_bundle(
        capture_batch_id=capture_batch_id,
        inventory_evidence=evidence,
        sweep_payloads=sweep_payloads,
        source_endpoint="yeusoft.report.inventory_outin",
        account_context={"dept_code": "A0190248"},
    )

    with get_capture_engine().begin() as connection:
        rows = connection.execute(
            select(capture_endpoint_payloads)
            .where(capture_endpoint_payloads.c.capture_batch_id == capture_batch_id)
            .order_by(capture_endpoint_payloads.c.id.asc())
        ).mappings().all()

    assert bundle["outin_report"]["capture_admission_ready"] is True
    assert bundle["outin_report"]["capture_parameter_plan"]["doctype_values"] == ["1", "2", "7"]
    assert bundle["outin_report"]["capture_write_summary"]["capture_write_complete"] is True
    assert len(rows) == 36
    assert rows[0]["source_endpoint"] == "yeusoft.report.inventory_outin"
    assert rows[1]["source_endpoint"] == INVENTORY_INOUT_DOCUMENTS_ENDPOINT
