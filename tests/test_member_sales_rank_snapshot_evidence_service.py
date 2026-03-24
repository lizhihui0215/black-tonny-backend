from __future__ import annotations

from app.services.research.member_sales_rank_snapshot_evidence import (
    build_member_sales_rank_snapshot_http_evidence_chain,
)


def _payload(count: int, rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "errcode": "1000",
        "retdata": {
            "Count": count,
            "Data": rows,
        },
    }


def test_build_member_sales_rank_snapshot_http_evidence_chain_marks_snapshot_ready() -> None:
    result = build_member_sales_rank_snapshot_http_evidence_chain(
        member_sales_rank_baseline_payload=_payload(
            2,
            [
                {"VipCardID": "V001", "TM": 299.0},
                {"VipCardID": "V002", "TM": 199.0},
            ],
        ),
        baseline_request_payload={"bdate": "20250301", "edate": "20260401", "page": 0, "pagesize": 0},
        page_probe_results={
            "page_0_pagesize_20_rows": 2,
            "page_1_pagesize_20_rows": 1,
            "page_1_pagesize_0_rows": 2,
        },
    )

    detail = result["member_sales_rank_snapshot"]
    assert detail["capture_parameter_plan"]["page_mode"] == "page_zero_full_fetch"
    assert detail["capture_parameter_plan"]["declared_total_count"] == 2
    assert detail["capture_parameter_plan"]["observed_total_rows"] == 2
    assert detail["capture_admission_ready"] is True
    assert detail["blocking_issues"] == []


def test_build_member_sales_rank_snapshot_http_evidence_chain_keeps_blocker_when_page_zero_not_proven() -> None:
    result = build_member_sales_rank_snapshot_http_evidence_chain(
        member_sales_rank_baseline_payload=_payload(
            5,
            [
                {"VipCardID": "V001", "TM": 299.0},
                {"VipCardID": "V002", "TM": 199.0},
            ],
        ),
        baseline_request_payload={"bdate": "20250301", "edate": "20260401", "page": 0, "pagesize": 0},
        page_probe_results={
            "page_0_pagesize_20_rows": 2,
            "page_1_pagesize_20_rows": 2,
            "page_1_pagesize_0_rows": 2,
        },
    )

    detail = result["member_sales_rank_snapshot"]
    assert detail["capture_admission_ready"] is False
    assert "当前单请求返回行数仍低于服务端声明总数" in detail["blocking_issues"]
