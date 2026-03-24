from __future__ import annotations

from app.services.research.daily_payment_snapshot_evidence import (
    build_daily_payment_snapshot_http_evidence_chain,
)


def _payload(rows: list[list[object]]) -> dict[str, object]:
    return {
        "Success": True,
        "Code": 200,
        "Data": {
            "Columns": ["DocNo", "Money"],
            "List": rows,
        },
    }


def test_build_daily_payment_snapshot_http_evidence_chain_marks_snapshot_ready_when_searchtype_same_dataset() -> None:
    result = build_daily_payment_snapshot_http_evidence_chain(
        daily_payment_baseline_payload=_payload([["A001", 100], ["A002", 80]]),
        baseline_request_payload={
            "MenuID": "E004006001",
            "SearchType": "1",
            "Search": "",
            "LastDate": "",
            "BeginDate": "2025-03-01",
            "EndDate": "2026-04-01",
        },
        searchtype_seed_results={
            "": {"semantics": "same_dataset"},
            "1": {"semantics": "same_dataset"},
            "2": {"semantics": "same_dataset"},
        },
    )

    detail = result["daily_payment_snapshot"]
    assert detail["baseline"]["row_count"] == 2
    assert detail["capture_parameter_plan"]["page_mode"] == "single_request_no_pagination_fields"
    assert detail["capture_parameter_plan"]["searchtype_semantics"]["same_dataset_for_tested_values"] is True
    assert detail["capture_admission_ready"] is True
    assert detail["blocking_issues"] == []


def test_build_daily_payment_snapshot_http_evidence_chain_keeps_blocker_when_searchtype_differs() -> None:
    result = build_daily_payment_snapshot_http_evidence_chain(
        daily_payment_baseline_payload=_payload([["A001", 100], ["A002", 80]]),
        baseline_request_payload={"MenuID": "E004006001", "SearchType": "1"},
        searchtype_seed_results={
            "1": {"semantics": "same_dataset"},
            "2": {"semantics": "different_dataset"},
        },
    )

    detail = result["daily_payment_snapshot"]
    assert detail["capture_admission_ready"] is False
    assert "SearchType seed 当前仍未收成同一数据集" in detail["blocking_issues"]
