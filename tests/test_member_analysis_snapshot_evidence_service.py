from __future__ import annotations

from app.services.research.member_analysis_snapshot_evidence import (
    build_member_analysis_snapshot_http_evidence_chain,
)


def _payload(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "errcode": "1000",
        "retdata": rows,
    }


def test_build_member_analysis_snapshot_http_evidence_chain_marks_snapshot_ready() -> None:
    result = build_member_analysis_snapshot_http_evidence_chain(
        member_analysis_baseline_payload=_payload(
            [
                {"VipCardID": "V001", "SaleMoney": 299.0},
                {"VipCardID": "V002", "SaleMoney": 199.0},
            ],
        ),
        baseline_request_payload={"salebdate": "20250301", "saleedate": "20250401", "page": 0, "pagesize": 0, "tag": "", "type": ""},
        page_probe_results={
            "page_0_pagesize_20_rows": 2,
            "page_1_pagesize_20_rows": 1,
            "page_1_pagesize_0_rows": 2,
        },
        type_seed_results={
            "blank": {"semantics": "same_dataset"},
            "1": {"semantics": "same_dataset"},
            "2": {"semantics": "same_dataset"},
            "3": {"semantics": "same_dataset"},
        },
        tag_seed_results={
            "blank": {"semantics": "same_dataset"},
            "1": {"semantics": "different_dataset"},
            "2": {"semantics": "different_dataset"},
            "3": {"semantics": "different_dataset"},
        },
    )

    detail = result["member_analysis_snapshot"]
    assert detail["capture_parameter_plan"]["page_mode"] == "page_zero_full_fetch"
    assert detail["capture_parameter_plan"]["type_semantics"]["same_dataset_for_tested_values"] is True
    assert detail["capture_parameter_plan"]["tag_semantics"]["different_dataset_values"] == ["1", "2", "3"]
    assert detail["capture_admission_ready"] is True
    assert detail["blocking_issues"] == []


def test_build_member_analysis_snapshot_http_evidence_chain_keeps_blocker_when_page_zero_not_proven() -> None:
    result = build_member_analysis_snapshot_http_evidence_chain(
        member_analysis_baseline_payload=_payload(
            [
                {"VipCardID": "V001", "SaleMoney": 299.0},
                {"VipCardID": "V002", "SaleMoney": 199.0},
            ],
        ),
        baseline_request_payload={"salebdate": "20250301", "saleedate": "20250401", "page": 0, "pagesize": 0, "tag": "", "type": ""},
        page_probe_results={
            "page_0_pagesize_20_rows": 1,
            "page_1_pagesize_20_rows": 1,
            "page_1_pagesize_0_rows": 2,
        },
        type_seed_results={"blank": {"semantics": "same_dataset"}},
        tag_seed_results={"blank": {"semantics": "same_dataset"}},
    )

    detail = result["member_analysis_snapshot"]
    assert detail["capture_admission_ready"] is False
    assert "尚未确认 page=0 是否稳定触发全量模式" in detail["blocking_issues"]
