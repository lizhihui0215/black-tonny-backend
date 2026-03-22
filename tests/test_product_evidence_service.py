from __future__ import annotations

from app.services.product_evidence_service import build_product_http_evidence_chain


def _table_payload(rows: list[dict[str, object]]) -> dict:
    return {
        "retdata": [
            {
                "Data": rows,
            }
        ]
    }


def test_build_product_http_evidence_chain_marks_pagination_and_exact_search() -> None:
    baseline = _table_payload(
        [
            {"SpeNum": "A001", "WareName": "One", "RetailPrice": "99.00"},
            {"SpeNum": "A002", "WareName": "Two", "RetailPrice": "109.00"},
        ]
    )
    page_payloads = {
        "2": _table_payload(
            [
                {"SpeNum": "A003", "WareName": "Three", "RetailPrice": "119.00"},
                {"SpeNum": "A004", "WareName": "Four", "RetailPrice": "129.00"},
            ]
        )
    }
    pagesize_payloads = {
        "60": baseline,
        "100": _table_payload(
            [
                {"SpeNum": "A001", "WareName": "One", "RetailPrice": "99.00"},
                {"SpeNum": "A002", "WareName": "Two", "RetailPrice": "109.00"},
                {"SpeNum": "A003", "WareName": "Three", "RetailPrice": "119.00"},
            ]
        ),
    }
    spenum_payloads = {
        "A001": _table_payload([{"SpeNum": "A001", "WareName": "One", "RetailPrice": "99.00"}]),
        "TOX1": _table_payload(
            [
                {"SpeNum": "TOX1A001", "WareName": "Subset One", "RetailPrice": "99.00"},
                {"SpeNum": "TOX1A002", "WareName": "Subset Two", "RetailPrice": "109.00"},
            ]
        ),
        "missing": _table_payload([]),
    }

    result = build_product_http_evidence_chain(
        product_baseline_payload=baseline,
        product_page_payloads=page_payloads,
        product_pagesize_payloads=pagesize_payloads,
        product_spenum_payloads=spenum_payloads,
    )

    product_list = result["product_list"]
    assert product_list["baseline"]["row_count"] == 2
    assert product_list["parameter_semantics"]["page"]["semantics"] == "pagination_page_switch"
    assert product_list["parameter_semantics"]["spenum"]["semantics"] == "scope_or_date_boundary"
    assert product_list["pagesize_probe_summary"]["recommended_pagesize"] == 100
    assert product_list["search_behavior"]["exact_match_values"] == ["A001"]
    assert product_list["search_behavior"]["broad_match_values"] == ["TOX1"]
    assert product_list["search_behavior"]["zero_match_values"] == ["missing"]
    assert product_list["capture_parameter_plan"]["page_mode"] == "sequential_pagination"
    assert product_list["capture_admission_ready"] is False
    assert product_list["blocking_issues"] == ["warecause 语义仍待确认"]
    assert result["conclusion"]["product_list_mainline_ready"] is False
