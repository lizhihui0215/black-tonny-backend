from __future__ import annotations

from app.services.inventory_evidence_service import build_inventory_http_evidence_chain


def _table_payload(columns: list[str], rows: list[list[object]]) -> dict:
    return {
        "retdata": [
            {
                "ColumnsList": columns,
                "Data": rows,
            }
        ]
    }


def test_build_inventory_http_evidence_chain_classifies_inventory_and_outin_parameters() -> None:
    inventory_baseline = _table_payload(["Sku", "Qty", "RetailPrice"], [["SKU-1", 5, 100], ["SKU-2", 4, 120]])
    inventory_stockflag_payloads = {
        "0": inventory_baseline,
        "1": _table_payload(["Sku", "Qty", "RetailPrice"], [["SKU-1", 5, 100], ["SKU-3", 2, 88], ["SKU-4", 1, 66]]),
        "2": _table_payload(["Sku", "Qty", "RetailPrice"], [["SKU-1", 5, 100], ["SKU-3", 2, 88], ["SKU-4", 1, 66]]),
    }
    inventory_page_payloads = {
        "0": _table_payload(["Sku", "Qty", "RetailPrice"], [["SKU-5", 1, 77]]),
        "1": _table_payload(["Sku", "Qty", "RetailPrice"], [["SKU-6", 1, 77]]),
        "2": _table_payload(["Sku", "Qty", "RetailPrice"], [["SKU-7", 1, 77]]),
    }

    outin_baseline = _table_payload(["DocNo", "Qty", "Amount"], [["D-1", 2, 20], ["D-2", 1, 10]])
    outin_datetype_payloads = {
        "1": outin_baseline,
        "2": _table_payload(["DocNo", "Qty", "Amount"], [["D-3", 2, 22], ["D-4", 1, 12]]),
    }
    outin_type_payloads = {
        "已出库": _table_payload(["DocNo", "Qty", "Amount"], [["D-9", 5, 50]]),
    }
    outin_doctype_payloads = {
        "1": _table_payload(["DocNo", "Qty", "Amount"], [["D-7", 3, 30]]),
    }

    result = build_inventory_http_evidence_chain(
        inventory_detail_baseline_payload=inventory_baseline,
        inventory_detail_stockflag_payloads=inventory_stockflag_payloads,
        inventory_detail_page_payloads=inventory_page_payloads,
        outin_baseline_payload=outin_baseline,
        outin_datetype_payloads=outin_datetype_payloads,
        outin_type_payloads=outin_type_payloads,
        outin_doctype_payloads=outin_doctype_payloads,
    )

    inventory_semantics = result["inventory_detail"]["parameter_semantics"]
    assert inventory_semantics["stockflag"]["semantics"] == "data_subset_or_scope_switch"
    assert inventory_semantics["page"]["semantics"] == "pagination_page_switch"
    assert set(inventory_semantics["page"]["by_stockflag"]) == {"0", "1", "2"}
    assert inventory_semantics["page"]["interpretation"]["kind"] == "server_side_pagination"
    assert result["inventory_detail"]["stockflag_equivalence"]["stockflag_1_equals_2"] is True

    outin_semantics = result["outin_report"]["parameter_semantics"]
    assert outin_semantics["datetype"]["semantics"] == "data_subset_or_scope_switch"
    assert outin_semantics["type"]["semantics"] == "data_subset_or_scope_switch"
    assert outin_semantics["doctype"]["semantics"] == "data_subset_or_scope_switch"
    assert result["outin_report"]["type_sweep_summary"]["recommended_distinct_values"] == ["已出库"]
    assert result["outin_report"]["doctype_sweep_summary"]["recommended_distinct_values"] == ["1"]

    assert result["issue_flags"] == []
    assert result["conclusion"]["inventory_detail_mainline_ready"] is True
    assert result["conclusion"]["outin_mainline_ready"] is True
