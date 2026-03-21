from __future__ import annotations

import json
from pathlib import Path

from app.services.erp_research_service import (
    analyze_response_sample,
    build_exploration_cases,
    build_report_matrix,
    classify_filter_fields,
    get_exploration_strategy,
    should_persist_capture,
    summarize_exploration_results,
)


def test_classify_sales_payload_filters():
    payload = {
        "menuid": "E004001008",
        "gridid": "E004001008_2",
        "parameter": {
            "BeginDate": "20250301",
            "Depart": "'A0190248'",
            "EndDate": "20260401",
            "Operater": "",
            "Tiem": "1",
            "WareClause": "",
        },
    }

    result = classify_filter_fields(payload)

    assert {item["path"] for item in result["date_fields"]} == {"parameter.BeginDate", "parameter.EndDate"}
    assert {item["path"] for item in result["organization_fields"]} >= {
        "parameter.Depart",
        "parameter.Operater",
        "parameter.WareClause",
    }
    assert {item["path"] for item in result["enum_fields"]} == {"parameter.Tiem"}
    assert {item["path"] for item in result["diy_context_fields"]} >= {"menuid", "gridid"}


def test_analyze_response_sample_detects_empty_cost_fields(tmp_path: Path):
    sample = {
        "errcode": 0,
        "retdata": {
            "ColumnsList": ["吊牌价", "吊牌金额", "成本价"],
            "Data": [
                [108.0, 108.0, None],
                [64.0, 64.0, None],
            ],
            "ExtraData": [],
        },
    }
    sample_path = tmp_path / "销售清单.json"
    sample_path.write_text(json.dumps(sample, ensure_ascii=False), "utf-8")

    result = analyze_response_sample(sample_path)

    assert result["response_shape"] == "retdata.ColumnsList+Data"
    assert result["row_count"] == 2
    assert any(field["field"] == "成本价" and field["non_null_count"] == 0 for field in result["cost_fields"])
    assert any(field["field"] == "吊牌价" and field["non_null_count"] == 2 for field in result["price_fields"])


def test_build_report_matrix_uses_latest_raw_sample(tmp_path: Path):
    report_doc = tmp_path / "report_api_samples.md"
    report_doc.write_text(
        """
### 销售清单

```bash
curl 'https://erpapistaging.yeusoft.net/FxErpApi/FXDIYReport/GetDIYReportData' \\
  --data-raw '{"menuid":"E004001008","gridid":"E004001008_2","parameter":{"BeginDate":"20250301","Depart":"A0190248","EndDate":"20260401","Operater":"","Tiem":"1","WareClause":""}}'
```
""".strip(),
        "utf-8",
    )

    raw_root = tmp_path / "raw"
    run_dir = raw_root / "20260321-205200"
    run_dir.mkdir(parents=True)
    (run_dir / "销售清单.json").write_text(
        json.dumps(
            {
                "errcode": 0,
                "retdata": {
                    "ColumnsList": ["吊牌价", "成本价"],
                    "Data": [[108.0, None]],
                    "ExtraData": [],
                },
            },
            ensure_ascii=False,
        ),
        "utf-8",
    )

    matrix = build_report_matrix(report_doc, raw_root)

    assert len(matrix) == 1
    entry = matrix[0]
    assert entry["title"] == "销售清单"
    assert entry["auth_mode"] == "token"
    assert entry["domain"] == "sales"
    assert "DIY 报表隐藏条件" in entry["risk_labels"]
    assert entry["capture_strategy"] == "枚举 sweep"
    assert entry["sample_analysis"]["row_count"] == 1


def test_analyze_response_sample_supports_title_data_shape(tmp_path: Path):
    sample = {
        "errcode": 0,
        "retdata": [
            {
                "Count": 975,
                "HJ": [],
                "Title": [{"RetailPrice": "零售价"}],
                "Data": [
                    {"RetailPrice": "228.00", "DeptName": "门店A"},
                    {"RetailPrice": "368.00", "DeptName": "门店A"},
                ],
            }
        ],
    }
    sample_path = tmp_path / "库存明细统计.json"
    sample_path.write_text(json.dumps(sample, ensure_ascii=False), "utf-8")

    result = analyze_response_sample(sample_path)

    assert result["response_shape"] == "retdata[].Title+Data"
    assert result["row_count"] == 2
    assert any(field["field"] == "RetailPrice" and field["non_null_count"] == 2 for field in result["price_fields"])


def test_build_exploration_cases_for_sales_list():
    report_spec = {
        "title": "销售清单",
        "payload": {
            "menuid": "E004001008",
            "gridid": "E004001008_2",
            "parameter": {
                "BeginDate": "20250301",
                "Depart": "A0190248",
                "EndDate": "20260401",
                "Operater": "",
                "Tiem": "1",
                "WareClause": "",
            },
        },
    }

    strategy = get_exploration_strategy("销售清单")
    assert strategy is not None
    cases = build_exploration_cases(report_spec, strategy, max_pages=2, enum_limit=3)

    tiem_values = {
        case["probe_context"].get("parameter.Tiem")
        for case in cases
        if case["kind"] == "enum"
    }
    assert tiem_values <= {"0", "1", "2"}
    assert "1" in tiem_values
    assert "2" in tiem_values
    assert all(case["payload"]["parameter"]["Depart"] == "A0190248" for case in cases)


def test_build_exploration_cases_for_inventory_detail_combines_stockflag_and_pages():
    report_spec = {
        "title": "库存明细统计",
        "payload": {
            "bdate": "20250301",
            "edate": "20260401",
            "stockflag": "0",
            "page": 0,
            "pagesize": 20,
        },
    }

    strategy = get_exploration_strategy("库存明细统计")
    assert strategy is not None
    cases = build_exploration_cases(report_spec, strategy, max_pages=2, enum_limit=2)

    stockflag_values = {
        case["probe_context"].get("stockflag")
        for case in cases
        if case["kind"] == "pagination"
    }
    page_values = {
        case["probe_context"].get("page")
        for case in cases
        if case["kind"] == "pagination"
    }
    assert stockflag_values == {"0", "1"}
    assert page_values == {0, 1}


def test_build_exploration_cases_for_outbound_doc_keeps_context_fields():
    report_spec = {
        "title": "出入库单据",
        "payload": {
            "bdate": "20250301",
            "edate": "20260401",
            "datetype": "1",
            "type": "已出库,已入库,在途",
            "doctype": "1,2,3,4,5,6,7",
            "page": 0,
            "pagesize": 0,
        },
    }

    strategy = get_exploration_strategy("出入库单据")
    assert strategy is not None
    cases = build_exploration_cases(report_spec, strategy, max_pages=2, enum_limit=2)

    datetype_values = {
        case["probe_context"].get("datetype")
        for case in cases
        if case["kind"] == "pagination"
    }
    assert datetype_values == {"1", "2"}
    assert all(case["payload"]["type"] == "已出库,已入库,在途" for case in cases)
    assert all(case["payload"]["doctype"] == "1,2,3,4,5,6,7" for case in cases)


def test_should_persist_capture_defaults_false_in_explore_mode():
    assert should_persist_capture("explore", skip_db=False, persist_detection=False) is False
    assert should_persist_capture("explore", skip_db=False, persist_detection=True) is True
    assert should_persist_capture("fetch", skip_db=False, persist_detection=False) is True
    assert should_persist_capture("fetch", skip_db=True, persist_detection=True) is False


def test_summarize_exploration_results_infers_risk_labels():
    strategy = get_exploration_strategy("库存明细统计")
    assert strategy is not None

    summary = summarize_exploration_results(
        strategy,
        [
            {
                "probe_context": {"stockflag": "0", "page": 0, "pagesize": 20},
                "analysis": {
                    "row_count": 975,
                    "column_count": 21,
                    "response_shape": "retdata[].Title+Data",
                    "row_signature": "sig-stockflag-0",
                },
            },
            {
                "probe_context": {"stockflag": "1", "page": 0, "pagesize": 20},
                "analysis": {
                    "row_count": 1548,
                    "column_count": 21,
                    "response_shape": "retdata[].Title+Data",
                    "row_signature": "sig-stockflag-1-page0",
                },
            },
            {
                "probe_context": {"stockflag": "1", "page": 1, "pagesize": 20},
                "analysis": {
                    "row_count": 1548,
                    "column_count": 21,
                    "response_shape": "retdata[].Title+Data",
                    "row_signature": "sig-stockflag-1-page1",
                },
            },
        ],
    )

    assert summary["recommended_capture_strategy"] == "枚举 sweep"
    assert summary["found_additional_pages"] is True
    assert summary["found_distinct_enum_results"] is True
    assert summary["risk_labels"] == ["需要扫枚举", "需要翻页"]
