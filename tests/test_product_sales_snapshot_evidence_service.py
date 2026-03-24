from __future__ import annotations

from app.services.research.product_sales_snapshot_evidence import (
    build_product_sales_snapshot_http_evidence_chain,
)


def _payload(count: int, rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "errcode": "1000",
        "retdata": {
            "Count": count,
            "Data": rows,
        },
    }


def test_build_product_sales_snapshot_http_evidence_chain_marks_single_request_complete() -> None:
    result = build_product_sales_snapshot_http_evidence_chain(
        product_sales_baseline_payload=_payload(
            2,
            [
                {"WareCode": "W001", "SaleAmount": 3, "SaleMoney": 299.0},
                {"WareCode": "W002", "SaleAmount": 1, "SaleMoney": 99.0},
            ],
        ),
        baseline_request_payload={"bdate": "20250301", "edate": "20260401", "warecause": "", "spenum": ""},
    )

    detail = result["product_sales_snapshot"]
    assert detail["baseline"]["row_count"] == 2
    assert detail["capture_parameter_plan"]["page_mode"] == "single_request_declared_total_match"
    assert detail["capture_parameter_plan"]["declared_total_count"] == 2
    assert detail["capture_parameter_plan"]["observed_total_rows"] == 2
    assert detail["capture_admission_ready"] is True
    assert detail["blocking_issues"] == []


def test_build_product_sales_snapshot_http_evidence_chain_keeps_blocker_when_rows_do_not_cover_declared_total() -> None:
    result = build_product_sales_snapshot_http_evidence_chain(
        product_sales_baseline_payload=_payload(
            5,
            [
                {"WareCode": "W001", "SaleAmount": 3, "SaleMoney": 299.0},
                {"WareCode": "W002", "SaleAmount": 1, "SaleMoney": 99.0},
            ],
        ),
        baseline_request_payload={"bdate": "20250301", "edate": "20260401", "warecause": "", "spenum": ""},
    )

    detail = result["product_sales_snapshot"]
    assert detail["capture_admission_ready"] is False
    assert "当前单请求返回行数仍低于服务端声明总数" in detail["blocking_issues"]
