from __future__ import annotations

import json
from pathlib import Path

from app.services.erp_research_service import (
    analyze_response_payload,
    analyze_response_sample,
    analyze_grid_view_payload,
    build_sales_menu_grain_analysis,
    build_sales_head_line_join_analysis,
    classify_http_probe_semantics,
    build_first_page_size_probe_cases,
    build_exploration_cases,
    build_report_matrix,
    classify_filter_fields,
    extract_normalized_table_rows,
    get_exploration_strategy,
    resolve_first_page_probe_sizes,
    should_trigger_edge_page_probe,
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
    assert result["columns_signature"]


def test_analyze_response_payload_builds_order_insensitive_row_set_signature():
    payload_a = {
        "retdata": [
            {
                "Title": [{"RetailPrice": "零售价"}],
                "Data": [
                    {"RetailPrice": "228.00", "DeptName": "门店A"},
                    {"RetailPrice": "368.00", "DeptName": "门店B"},
                ],
            }
        ]
    }
    payload_b = {
        "retdata": [
            {
                "Title": [{"RetailPrice": "零售价"}],
                "Data": [
                    {"RetailPrice": "368.00", "DeptName": "门店B"},
                    {"RetailPrice": "228.00", "DeptName": "门店A"},
                ],
            }
        ]
    }

    result_a = analyze_response_payload(payload_a)
    result_b = analyze_response_payload(payload_b)

    assert result_a["row_signature"] != result_b["row_signature"]
    assert result_a["row_set_signature"] == result_b["row_set_signature"]


def test_analyze_response_sample_supports_retdata_nested_data_shape(tmp_path: Path):
    sample = {
        "errcode": 0,
        "retdata": [
            {
                "Count": "2",
                "HJ": [],
                "Data": [
                    {"DocNo": "BSD-0001", "TN": "2", "TRP": "123.00"},
                    {"DocNo": "BSD-0002", "TN": "3", "TRP": "456.00"},
                ],
            }
        ],
    }
    sample_path = tmp_path / "出入库单据.json"
    sample_path.write_text(json.dumps(sample, ensure_ascii=False), "utf-8")

    result = analyze_response_sample(sample_path)

    assert result["response_shape"] == "retdata[].Data"
    assert result["row_count"] == 2
    assert result["column_count"] == 3


def test_analyze_grid_view_payload_extracts_column_tokens():
    payload = {
        "Success": True,
        "Data": [
            {
                "GridID": "E004001008_1",
                "ViewID": "view-1",
                "ViewName": "按单据",
                "ViewList": [
                    {"GCode": "SaleNum", "GName": "销售单号", "GSort": 1},
                    {"GCode": "SaleDate", "GName": "销售日期", "GSort": 2},
                    {"GCode": "TotalSaleMoney", "GName": "销售金额", "GSort": 3},
                ],
            }
        ],
    }

    result = analyze_grid_view_payload(payload)

    assert result["response_shape"] == "Data[].ViewList"
    assert result["grid_id"] == "E004001008_1"
    assert result["column_count"] == 3
    assert "sale_no" in result["normalized_tokens"]
    assert "sales_amount" in result["normalized_tokens"]


def test_build_sales_menu_grain_analysis_identifies_header_and_detail_variants():
    document_grid_payload = {
        "Success": True,
        "Data": [
            {
                "GridID": "E004001008_1",
                "ViewList": [
                    {"GCode": "SaleNum", "GName": "销售单号"},
                    {"GCode": "SaleDate", "GName": "销售日期"},
                    {"GCode": "TotalSaleAmount", "GName": "销量"},
                    {"GCode": "TotalSaleMoney", "GName": "销售金额"},
                    {"GCode": "ReceiveMoney", "GName": "实收金额"},
                ],
            }
        ],
    }
    detail_grid_payload = {
        "Success": True,
        "Data": [
            {
                "GridID": "E004001008_2",
                "ViewList": [
                    {"GCode": "零售单号", "GName": "零售单号"},
                    {"GCode": "明细流水", "GName": "明细流水"},
                    {"GCode": "款号", "GName": "款号"},
                    {"GCode": "颜色", "GName": "颜色"},
                    {"GCode": "尺码", "GName": "尺码"},
                    {"GCode": "数量", "GName": "数量"},
                    {"GCode": "金额", "GName": "金额"},
                ],
            }
        ],
    }
    document_data_payload = {
        "errcode": 0,
        "retdata": [
            {
                "Count": 2,
                "Data": [
                    {
                        "SaleNum": "A0001",
                        "SaleDate": "2026-03-21",
                        "OperMan": "导购A",
                        "TotalSaleAmount": 2,
                        "TotalSaleMoney": "347.00",
                        "ReceiveMoney": "347.00",
                    }
                ],
            }
        ],
    }
    detail_data_payload = {
        "errcode": 0,
        "retdata": {
            "ColumnsList": ["零售单号", "明细流水", "款号", "颜色", "尺码", "数量", "金额"],
            "Data": [["A0001", "1", "K001", "粉", "90", 1, "199.00"]],
        },
    }

    result = build_sales_menu_grain_analysis(
        menuid="E004001008",
        document_grid_payload=document_grid_payload,
        detail_grid_payload=detail_grid_payload,
        document_data_payload=document_data_payload,
        detail_data_payload=detail_data_payload,
    )

    assert result["variants"]["document_grid"]["grain_kind"] == "document_header_schema"
    assert result["variants"]["detail_grid"]["grain_kind"] == "line_detail_schema"
    assert result["variants"]["document_data"]["grain_kind"] == "document_header_candidate"
    assert result["variants"]["detail_data"]["grain_kind"] == "line_detail_candidate"
    assert result["conclusion"]["head_line_link_feasible"] is True
    assert "sale_no" in result["overlap"]["candidate_join_keys"]


def test_extract_normalized_table_rows_supports_list_and_mapping_shapes():
    payload = {
        "retdata": {
            "ColumnsList": ["零售单号", "数量", "金额"],
            "Data": [["A0001", 2, "99.00"]],
        }
    }

    rows = extract_normalized_table_rows(payload)

    assert rows == [{"sale_no": "A0001", "quantity": 2, "sales_amount": "99.00"}]


def test_build_sales_head_line_join_analysis_reports_sale_no_one_to_many():
    document_payload = {
        "retdata": [
            {
                "Data": [
                    {"SaleNum": "A0001", "SaleDate": "2026-03-21", "OperMan": "导购A"},
                    {"SaleNum": "A0002", "SaleDate": "2026-03-21", "OperMan": "导购B"},
                ]
            }
        ]
    }
    detail_payload = {
        "retdata": {
            "ColumnsList": ["零售单号", "明细流水", "款号", "数量", "金额"],
            "Data": [
                ["A0001", "1", "K001", 1, "50.00"],
                ["A0001", "2", "K002", 1, "49.00"],
                ["A0002", "1", "K003", 2, "88.00"],
            ],
        }
    }

    result = build_sales_head_line_join_analysis(
        document_payload=document_payload,
        detail_payload=detail_payload,
    )

    assert result["sale_no_head_line_link_stable"] is True
    sale_no = next(item for item in result["candidate_keys"] if item["key"] == "sale_no")
    assert sale_no["relationship"] == "one_to_many"
    assert sale_no["stable_candidate"] is True
    assert "detail_serial" in result["field_ownership"]["detail_only"]


def test_classify_http_probe_semantics_distinguishes_same_dataset_and_scope_boundary():
    baseline = {
        "row_count": 100,
        "columns_signature": "cols-a",
        "row_set_signature": "rows-a",
    }

    same_dataset = classify_http_probe_semantics(
        parameter_path="parameter.Tiem",
        baseline_analysis=baseline,
        variants=[
            {
                "value": "0",
                "row_count": 100,
                "columns_signature": "cols-a",
                "row_set_signature": "rows-a",
            },
            {
                "value": "2",
                "row_count": 100,
                "columns_signature": "cols-a",
                "row_set_signature": "rows-a",
            },
        ],
    )
    scope_boundary = classify_http_probe_semantics(
        parameter_path="parameter.BeginDate",
        baseline_analysis=baseline,
        variants=[
            {
                "value": "20260401",
                "row_count": 0,
                "columns_signature": "cols-a",
                "row_set_signature": "rows-b",
            }
        ],
    )
    page_switch = classify_http_probe_semantics(
        parameter_path="page",
        baseline_analysis=baseline,
        variants=[
            {
                "value": 1,
                "row_count": 20,
                "columns_signature": "cols-a",
                "row_set_signature": "rows-c",
            }
        ],
    )

    assert same_dataset["semantics"] == "same_dataset"
    assert same_dataset["mainline_ready"] is True
    assert scope_boundary["semantics"] == "scope_or_date_boundary"
    assert scope_boundary["recommended_http_strategy"] == "date_or_scope_parameter"
    assert page_switch["semantics"] == "pagination_page_switch"


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


def test_build_exploration_cases_include_first_page_size_probe_and_edge_sizes():
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
    cases = build_exploration_cases(
        report_spec,
        strategy,
        max_pages=1,
        enum_limit=1,
        edge_page_sizes=[50000],
    )

    probed_sizes = {
        case["probe_context"].get("pagesize")
        for case in cases
        if case["kind"] == "page_size_probe"
    }
    assert probed_sizes == {0, 20, 100, 1000, 10000, 50000}


def test_build_first_page_size_probe_cases_only_contains_requested_edge_sizes():
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
    cases = build_first_page_size_probe_cases(
        report_spec,
        strategy,
        probe_sizes=[50000, 100000],
    )

    assert {case["probe_context"]["pagesize"] for case in cases} == {50000, 100000}


def test_build_exploration_cases_skip_first_page_size_probe_without_pagination():
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
    cases = build_exploration_cases(
        report_spec,
        strategy,
        max_pages=1,
        enum_limit=2,
        edge_page_sizes=[50000],
    )

    assert not [case for case in cases if case["kind"] == "page_size_probe"]


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


def test_resolve_first_page_probe_sizes_keeps_defaults_and_appends_edge_sizes():
    assert resolve_first_page_probe_sizes(edge_candidates=[50000, 100000, 10000]) == (
        20,
        100,
        1000,
        10000,
        0,
        50000,
        100000,
    )


def test_should_trigger_edge_page_probe_only_when_threshold_hit():
    assert should_trigger_edge_page_probe(
        {
            "tested_page_sizes": [
                {"page_size": 20, "row_count": 20},
                {"page_size": 10000, "row_count": 9999},
            ]
        }
    ) is False
    assert should_trigger_edge_page_probe(
        {
            "tested_page_sizes": [
                {"page_size": 20, "row_count": 20},
                {"page_size": 10000, "row_count": 10000},
            ]
        }
    ) is True


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


def test_summarize_exploration_results_marks_large_pages_ignored_when_signature_same():
    strategy = get_exploration_strategy("零售明细统计")
    assert strategy is not None

    summary = summarize_exploration_results(
        strategy,
        [
            {
                "kind": "page_size_probe",
                "probe_context": {"page": 0, "pagesize": 20},
                "status": 200,
                "analysis": {
                    "row_count": 1352,
                    "column_count": 21,
                    "columns_signature": "cols-1",
                    "response_shape": "retdata[].Title+Data",
                    "row_signature": "sig-full",
                    "row_set_signature": "set-full",
                },
            },
            {
                "kind": "page_size_probe",
                "probe_context": {"page": 0, "pagesize": 1000},
                "status": 200,
                "analysis": {
                    "row_count": 1352,
                    "column_count": 21,
                    "columns_signature": "cols-1",
                    "response_shape": "retdata[].Title+Data",
                    "row_signature": "sig-full",
                    "row_set_signature": "set-full",
                },
            },
            {
                "kind": "page_size_probe",
                "probe_context": {"page": 0, "pagesize": 10000},
                "status": 200,
                "analysis": {
                    "row_count": 1352,
                    "column_count": 21,
                    "columns_signature": "cols-1",
                    "response_shape": "retdata[].Title+Data",
                    "row_signature": "sig-full",
                    "row_set_signature": "set-full",
                },
            },
            {
                "kind": "page_size_probe",
                "probe_context": {"page": 0, "pagesize": 0},
                "status": 200,
                "analysis": {
                    "row_count": 1352,
                    "column_count": 21,
                    "columns_signature": "cols-1",
                    "response_shape": "retdata[].Title+Data",
                    "row_signature": "sig-full",
                    "row_set_signature": "set-full",
                },
            },
        ],
    )

    probe = summary["first_page_size_probe"]
    assert probe["recommended_first_page_size"] == 20
    assert probe["first_page_contains_full_dataset"] is True
    assert probe["large_page_ignored"] is True
    assert probe["large_page_supported"] is False


def test_summarize_exploration_results_can_recommend_larger_first_page_size():
    strategy = get_exploration_strategy("库存明细统计")
    assert strategy is not None

    summary = summarize_exploration_results(
        strategy,
        [
            {
                "kind": "page_size_probe",
                "probe_context": {"page": 0, "pagesize": 20},
                "status": 200,
                "analysis": {
                    "row_count": 20,
                    "column_count": 21,
                    "columns_signature": "cols-1",
                    "response_shape": "retdata[].Title+Data",
                    "row_signature": "sig-page20",
                    "row_set_signature": "set-page20",
                },
            },
            {
                "kind": "page_size_probe",
                "probe_context": {"page": 0, "pagesize": 1000},
                "status": 200,
                "analysis": {
                    "row_count": 975,
                    "column_count": 21,
                    "columns_signature": "cols-1",
                    "response_shape": "retdata[].Title+Data",
                    "row_signature": "sig-page1000",
                    "row_set_signature": "set-page1000",
                },
            },
            {
                "kind": "page_size_probe",
                "probe_context": {"page": 0, "pagesize": 10000},
                "status": 200,
                "analysis": {
                    "row_count": 975,
                    "column_count": 21,
                    "columns_signature": "cols-1",
                    "response_shape": "retdata[].Title+Data",
                    "row_signature": "sig-page1000",
                    "row_set_signature": "set-page1000",
                },
            },
            {
                "kind": "page_size_probe",
                "probe_context": {"page": 0, "pagesize": 0},
                "status": 200,
                "analysis": {
                    "row_count": 975,
                    "column_count": 21,
                    "columns_signature": "cols-1",
                    "response_shape": "retdata[].Title+Data",
                    "row_signature": "sig-page1000",
                    "row_set_signature": "set-page1000",
                },
            },
        ],
    )

    probe = summary["first_page_size_probe"]
    assert probe["recommended_first_page_size"] == 1000
    assert probe["large_page_supported"] is True
    assert probe["large_page_ignored"] is False


def test_summarize_exploration_results_classifies_enum_as_data_subset_switch():
    strategy = get_exploration_strategy("库存明细统计")
    assert strategy is not None

    summary = summarize_exploration_results(
        strategy,
        [
            {
                "kind": "pagination",
                "probe_context": {"stockflag": "0", "page": 0, "pagesize": 20},
                "analysis": {
                    "row_count": 975,
                    "column_count": 88,
                    "columns_signature": "cols-stock",
                    "response_shape": "retdata[].Title+Data",
                    "row_signature": "sig-0",
                    "row_set_signature": "set-0",
                },
            },
            {
                "kind": "pagination",
                "probe_context": {"stockflag": "1", "page": 0, "pagesize": 20},
                "analysis": {
                    "row_count": 1548,
                    "column_count": 88,
                    "columns_signature": "cols-stock",
                    "response_shape": "retdata[].Title+Data",
                    "row_signature": "sig-1",
                    "row_set_signature": "set-1",
                },
            },
        ],
    )

    semantics = summary["enum_probe_semantics"]
    assert semantics[0]["path"] == "stockflag"
    assert semantics[0]["classification"] == "data_subset_or_scope_switch"


def test_summarize_exploration_results_classifies_enum_as_view_switch():
    strategy = get_exploration_strategy("出入库单据")
    assert strategy is not None

    summary = summarize_exploration_results(
        strategy,
        [
            {
                "kind": "pagination",
                "probe_context": {"datetype": "1", "page": 0, "pagesize": 20},
                "analysis": {
                    "row_count": 311,
                    "column_count": 13,
                    "columns_signature": "cols-a",
                    "response_shape": "retdata[].Data",
                    "row_signature": "sig-a",
                    "row_set_signature": "set-same",
                },
            },
            {
                "kind": "pagination",
                "probe_context": {"datetype": "2", "page": 0, "pagesize": 20},
                "analysis": {
                    "row_count": 311,
                    "column_count": 14,
                    "columns_signature": "cols-b",
                    "response_shape": "retdata[].Data",
                    "row_signature": "sig-b",
                    "row_set_signature": "set-same",
                },
            },
        ],
    )

    semantics = summary["enum_probe_semantics"]
    assert semantics[0]["path"] == "datetype"
    assert semantics[0]["classification"] == "view_switch"
