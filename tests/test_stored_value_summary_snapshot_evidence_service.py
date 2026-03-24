from __future__ import annotations

from app.services.research.stored_value_summary_snapshot_evidence import (
    build_stored_value_by_store_snapshot_http_evidence_chain,
    build_stored_value_card_summary_snapshot_http_evidence_chain,
)


def _payload(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "errcode": "1000",
        "retdata": rows,
    }


def test_build_stored_value_card_summary_snapshot_http_evidence_chain_marks_snapshot_ready() -> None:
    result = build_stored_value_card_summary_snapshot_http_evidence_chain(
        stored_value_card_summary_baseline_payload=_payload(
            [
                {"VipCardID": "V001", "Balance": 299.0},
                {"VipCardID": "V002", "Balance": 199.0},
            ]
        ),
        baseline_request_payload={
            "menuid": "E004004004",
            "gridid": "E004004004_main",
            "parameter": {"BeginDate": "2025-03-01", "EndDate": "2026-04-01", "Search": ""},
        },
        page_probe_results={
            "page_0_pagesize_20_rows": 2,
            "page_1_pagesize_20_rows": 2,
            "page_1_pagesize_0_rows": 2,
        },
        search_seed_results={
            "__no_match__": {"semantics": "different_dataset"},
            "vip_card:V001": {"semantics": "different_dataset"},
        },
    )

    detail = result["stored_value_card_summary_snapshot"]
    assert detail["capture_parameter_plan"]["page_mode"] == "single_request_page_field_ignored"
    assert detail["capture_parameter_plan"]["search_semantics"]["different_dataset_values"] == ["__no_match__", "vip_card:V001"]
    assert detail["capture_admission_ready"] is True
    assert detail["blocking_issues"] == []


def test_build_stored_value_card_summary_snapshot_http_evidence_chain_keeps_blocker_when_page_changes() -> None:
    result = build_stored_value_card_summary_snapshot_http_evidence_chain(
        stored_value_card_summary_baseline_payload=_payload(
            [
                {"VipCardID": "V001", "Balance": 299.0},
                {"VipCardID": "V002", "Balance": 199.0},
            ]
        ),
        baseline_request_payload={
            "menuid": "E004004004",
            "gridid": "E004004004_main",
            "parameter": {"BeginDate": "2025-03-01", "EndDate": "2026-04-01", "Search": ""},
        },
        page_probe_results={
            "page_0_pagesize_20_rows": 2,
            "page_1_pagesize_20_rows": 1,
            "page_1_pagesize_0_rows": 2,
        },
        search_seed_results={"__no_match__": {"semantics": "different_dataset"}},
    )

    detail = result["stored_value_card_summary_snapshot"]
    assert detail["capture_admission_ready"] is False
    assert "尚未确认 page/pagesize 是否仍为同一数据集" in detail["blocking_issues"]


def test_build_stored_value_by_store_snapshot_http_evidence_chain_marks_snapshot_ready() -> None:
    result = build_stored_value_by_store_snapshot_http_evidence_chain(
        stored_value_by_store_baseline_payload=_payload([{"DeptCode": "A0190248", "Balance": 999.0}]),
        baseline_request_payload={
            "menuid": "E004004003",
            "gridid": "E004004003_main",
            "parameter": {"BeginDate": "2025-03-01", "EndDate": "2026-04-01"},
        },
        page_probe_results={
            "page_0_pagesize_20_rows": 1,
            "page_1_pagesize_20_rows": 1,
            "page_1_pagesize_0_rows": 1,
        },
    )

    detail = result["stored_value_by_store_snapshot"]
    assert detail["capture_parameter_plan"]["page_mode"] == "single_request_page_field_ignored"
    assert detail["capture_admission_ready"] is True
    assert detail["blocking_issues"] == []
