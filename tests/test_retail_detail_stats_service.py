from __future__ import annotations

from app.services.retail_detail_stats_service import (
    RETAIL_DETAIL_CANONICAL_ENDPOINT,
    build_sales_reconciliation_report,
    fetch_retail_detail_pages,
    normalize_retail_detail_rows,
)


def _retail_detail_payload(rows: list[dict[str, str | int | float]]) -> dict:
    return {
        "retdata": [
            {
                "Count": len(rows),
                "Hj": [],
                "Title": [{"col01": "%u0039%u0030%u003C%u0062%u0072%u002F%u003E%u5747%u7801"}],
                "Data": rows,
            }
        ]
    }


def test_fetch_retail_detail_pages_stops_on_repeated_signature():
    payloads = {
        0: _retail_detail_payload(
            [
                {
                    "DeptName": "门店A",
                    "WareName": "家居服A",
                    "Spec": "SKU-A",
                    "ColorName": "粉色",
                    "RetailPrice": "100",
                    "col01": "2",
                    "TotalMoney": "180",
                    "TotalNum": "2",
                    "TotalRetailMoney": "200",
                    "Discount": "0.9",
                    "Trade": "销售",
                }
            ]
        ),
        1: _retail_detail_payload(
            [
                {
                    "DeptName": "门店A",
                    "WareName": "家居服B",
                    "Spec": "SKU-B",
                    "ColorName": "蓝色",
                    "RetailPrice": "120",
                    "col01": "1",
                    "TotalMoney": "100",
                    "TotalNum": "1",
                    "TotalRetailMoney": "120",
                    "Discount": "0.83",
                    "Trade": "销售",
                }
            ]
        ),
        2: _retail_detail_payload(
            [
                {
                    "DeptName": "门店A",
                    "WareName": "家居服B",
                    "Spec": "SKU-B",
                    "ColorName": "蓝色",
                    "RetailPrice": "120",
                    "col01": "1",
                    "TotalMoney": "100",
                    "TotalNum": "1",
                    "TotalRetailMoney": "120",
                    "Discount": "0.83",
                    "Trade": "销售",
                }
            ]
        ),
    }

    result = fetch_retail_detail_pages(
        {"bdate": "20250301", "edate": "20260401", "page": 0, "pagesize": 0},
        lambda request_payload: (200, payloads[request_payload["page"]]),
        max_pages=5,
    )

    assert result.stop_reason == "repeated_signature"
    assert [page.page_no for page in result.pages] == [0, 1, 2]
    assert result.pages[-1].stop_reason == "repeated_signature"


def test_fetch_retail_detail_pages_stops_when_first_page_is_full_dataset():
    calls: list[int] = []

    result = fetch_retail_detail_pages(
        {"bdate": "20250301", "edate": "20260401", "page": 0, "pagesize": 0},
        lambda request_payload: (
            calls.append(request_payload["page"]) or 200,
            _retail_detail_payload(
                [
                    {
                        "DeptName": "门店A",
                        "WareName": f"家居服{index}",
                        "Spec": f"SKU-{index}",
                        "ColorName": "粉色",
                        "RetailPrice": "100",
                        "col01": "1",
                        "TotalMoney": "100",
                        "TotalNum": "1",
                        "TotalRetailMoney": "100",
                        "Discount": "1",
                        "Trade": "销售",
                    }
                    for index in range(25)
                ]
            ),
        ),
        max_pages=5,
    )

    assert calls == [0]
    assert result.stop_reason == "page_zero_contains_full_dataset"
    assert len(result.pages) == 1


def test_normalize_retail_detail_rows_extracts_totals():
    rows = normalize_retail_detail_rows(
        _retail_detail_payload(
            [
                {
                    "DeptName": "门店A",
                    "WareName": "家居服A",
                    "Spec": "SKU-A",
                    "ColorName": "粉色",
                    "RetailPrice": "100",
                    "col01": "2",
                    "TotalMoney": "180",
                    "TotalNum": "2",
                    "TotalRetailMoney": "200",
                    "Discount": "0.9",
                    "Trade": "销售",
                }
            ]
        )
    )

    assert rows[0]["store_name"] == "门店A"
    assert rows[0]["sku_code"] == "SKU-A"
    assert rows[0]["quantity_total"] == 2.0
    assert rows[0]["amount_total"] == 180.0
    assert rows[0]["retail_amount_total"] == 200.0
    assert rows[0]["size_breakdown"]["90 / 均码"] == 2.0


def test_build_sales_reconciliation_report_outputs_metric_statuses():
    retail_pages = fetch_retail_detail_pages(
        {"bdate": "20250301", "edate": "20260401", "page": 0, "pagesize": 0},
        lambda request_payload: (
            200,
            _retail_detail_payload(
                [
                    {
                        "DeptName": "门店A",
                        "WareName": "家居服A",
                        "Spec": "SKU-A",
                        "ColorName": "粉色",
                        "RetailPrice": "100",
                        "col01": "2",
                        "TotalMoney": "180",
                        "TotalNum": "2",
                        "TotalRetailMoney": "200",
                        "Discount": "0.9",
                        "Trade": "销售",
                    }
                ]
                if request_payload["page"] == 0
                else []
            ),
        ),
        max_pages=2,
    )
    sales_list_payload = {
        "retdata": {
            "ColumnsList": ["零售单号", "数量", "金额"],
            "Data": [
                ["A001", 1, 100],
                ["A002", 1, 80],
            ],
        }
    }

    report = build_sales_reconciliation_report(
        retail_pages=retail_pages,
        sales_list_payload=sales_list_payload,
        retail_request_payload={"bdate": "20250301", "edate": "20260401"},
        sales_request_payload={"parameter": {"BeginDate": "20250301", "EndDate": "20260401"}},
    )

    assert report["retail_detail_source_endpoint"] == RETAIL_DETAIL_CANONICAL_ENDPOINT
    assert report["retail_detail"]["summary"]["quantity_total"] == 2.0
    assert report["sales_list"]["summary"]["order_count"] == 2
    metric_map = {metric["metric"]: metric for metric in report["metrics"]}
    assert metric_map["quantity_total"]["status"] == "一致"
    assert metric_map["amount_total"]["status"] == "一致"
    assert metric_map["sales_list_order_count"]["status"] == "差异待解释"
