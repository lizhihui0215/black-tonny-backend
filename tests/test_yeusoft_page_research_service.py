from __future__ import annotations

import json
from pathlib import Path

from app.services.research.page_research import (
    build_page_scope_action_texts,
    build_page_scope_texts,
    build_menu_lookup,
    build_menu_coverage_registry_entries,
    build_page_manifest_summary,
    build_page_research_registry,
    build_unknown_page_registry_entries,
    build_single_variable_probe_cases,
    diff_payload_paths,
    get_probe_target_titles,
    list_menu_items,
    list_report_menu_items,
    summarize_page_manifests,
)


def test_build_page_research_registry_merges_report_doc_and_api_images(tmp_path: Path):
    report_doc = tmp_path / "report_api_samples.md"
    report_doc.write_text(
        """
### 销售清单
```bash
curl 'https://example.com/FxErpApi/FXDIYReport/GetDIYReportData' --data-raw '{"menuid":"E004001008","gridid":"E004001008_2"}'
```

### 库存明细统计
```bash
curl 'https://example.com/eposapi/YisEposReport/SelDeptStockWaitList' --data-raw '{"page":0,"pagesize":20}'
```
""".strip(),
        "utf-8",
    )
    api_images_dir = tmp_path / "API-images"
    api_images_dir.mkdir()
    (api_images_dir / "销售清单-1.png").write_bytes(b"fake")
    (api_images_dir / "会员中心-2.png").write_bytes(b"fake")
    (api_images_dir / "库存综合分析-按中分类-1.png").write_bytes(b"fake")

    registry = build_page_research_registry(report_doc, api_images_dir)
    titles = [item.title for item in registry]

    assert titles[:2] == ["销售清单", "库存明细统计"]
    assert "会员中心" in titles
    sales_entry = next(item for item in registry if item.title == "销售清单")
    assert sales_entry.image_evidence_count == 1
    assert sales_entry.sample_url.endswith("GetDIYReportData")
    assert sales_entry.recipe.query_required is True
    member_entry = next(item for item in registry if item.title == "会员中心")
    assert member_entry.menu_root_name == "会员资料"
    assert member_entry.menu_target_title == "会员中心"
    assert member_entry.target_menu_path == ("会员资料", "会员中心")

    inventory_variant = next(item for item in registry if item.title == "库存综合分析-按中分类")
    assert inventory_variant.menu_target_title == "库存综合分析"
    assert inventory_variant.menu_root_name == "报表管理"
    assert inventory_variant.group_name == "库存报表"
    assert inventory_variant.variant_label == "按中分类"
    assert inventory_variant.target_menu_path == ("报表管理", "库存报表", "库存综合分析")


def test_build_page_research_registry_assigns_custom_steps_for_receipt_and_stocktaking(tmp_path: Path):
    report_doc = tmp_path / "report_api_samples.md"
    report_doc.write_text("", "utf-8")
    api_images_dir = tmp_path / "images"
    api_images_dir.mkdir()
    (api_images_dir / "收货确认-1.png").write_bytes(b"fake")
    (api_images_dir / "门店盘点单-1.png").write_bytes(b"fake")

    registry = build_page_research_registry(report_doc, api_images_dir)

    receipt_entry = next(item for item in registry if item.title == "收货确认")
    stocktaking_entry = next(item for item in registry if item.title == "门店盘点单")

    receipt_steps = [(step.key, step.kind, step.target_text) for step in receipt_entry.recipe.steps]
    stocktaking_steps = [(step.key, step.kind, step.target_text) for step in stocktaking_entry.recipe.steps]

    assert ("click_receipt_confirm", "click_text", "单据确认") in receipt_steps
    assert ("click_receipt_logistics", "click_text", "物流信息") in receipt_steps
    assert ("select_receipt_row", "select_first_grid_row", None) in receipt_steps
    assert next(step.wait_ms for step in receipt_entry.recipe.steps if step.key == "query") == 5000

    assert ("click_stocktaking_detail", "click_text", "查看明细") in stocktaking_steps
    assert ("click_stocktaking_barcode_record", "click_text", "条码记录") in stocktaking_steps
    assert ("click_stocktaking_profit_loss", "click_text", "统计损溢") in stocktaking_steps
    assert ("click_stocktaking_new", "click_text", "新增") in stocktaking_steps
    assert next(step.wait_ms for step in stocktaking_entry.recipe.steps if step.key == "query") == 5000
    assert receipt_entry.as_dict()["scope_texts"] == ["收货确认"]
    assert stocktaking_entry.as_dict()["scope_texts"] == ["门店盘点单"]


def test_build_unknown_page_registry_entries_from_menu_coverage_payload(tmp_path: Path):
    report_doc = tmp_path / "report_api_samples.md"
    report_doc.write_text(
        """
### 销售清单
```bash
curl 'https://example.com/FxErpApi/FXDIYReport/GetDIYReportData' --data-raw '{"menuid":"E004001008","gridid":"E004001008_2"}'
```
""".strip(),
        "utf-8",
    )
    registry = build_page_research_registry(report_doc, tmp_path / "images")
    payload = {
        "pages": [
            {
                "title": "商品资料",
                "root_name": "基础资料",
                "group_name": "",
                "menu_path": ["基础资料", "商品资料"],
                "coverage_status": "visible_but_untracked",
            },
            {
                "title": "销售清单",
                "root_name": "报表管理",
                "group_name": "零售报表",
                "menu_path": ["报表管理", "零售报表", "销售清单"],
                "coverage_status": "visible_but_untracked",
            },
        ]
    }

    extra_entries = build_unknown_page_registry_entries(payload, existing_registry=registry)

    assert [entry.title for entry in extra_entries] == ["商品资料"]
    assert extra_entries[0].menu_root_name == "基础资料"
    assert extra_entries[0].target_menu_path == ("基础资料", "商品资料")


def test_build_menu_coverage_registry_entries_can_rehydrate_covered_page() -> None:
    payload = {
        "pages": [
            {
                "title": "商品资料",
                "root_name": "基础资料",
                "group_name": "",
                "menu_path": ["基础资料", "商品资料"],
                "coverage_status": "covered",
            },
            {
                "title": "客户资料",
                "root_name": "基础资料",
                "group_name": "",
                "menu_path": ["基础资料", "客户资料"],
                "coverage_status": "covered",
            },
        ]
    }

    entries = build_menu_coverage_registry_entries(
        payload,
        only_titles=["商品资料"],
    )

    assert [entry.title for entry in entries] == ["商品资料"]
    assert entries[0].menu_root_name == "基础资料"
    assert entries[0].target_menu_path == ("基础资料", "商品资料")


def test_list_report_menu_items_and_lookup_support_alias():
    menu_list = [
        {
            "FuncName": "报表管理",
            "FuncLID": "ROOT",
            "Children": [
                {
                    "FuncName": "零售报表",
                    "FuncLID": "E004000000",
                    "Children": [
                        {
                            "FuncName": "零售明细统计",
                            "FuncLID": "E004001001",
                            "FuncUrl": "report01",
                        }
                    ],
                }
            ],
        }
    ]

    items = list_report_menu_items(menu_list)
    lookup = build_menu_lookup(menu_list)

    assert len(items) == 1
    assert items[0]["canonicalName"] == "零售明细统计"
    assert lookup["零售明细统计"]["FuncUrl"] == "report01"
    assert lookup["销售明细统计"]["FuncUrl"] == "report01"


def test_list_report_menu_items_supports_sublist_structure():
    menu_list = [
        {
            "FuncName": "报表管理",
            "FuncLID": "E004",
            "SubList": [
                {
                    "FuncName": "库存报表",
                    "FuncLID": "E004002",
                    "SubList": [
                        {
                            "FuncName": "库存明细统计",
                            "FuncLID": "E004002001",
                            "FuncUrl": "StockList",
                        }
                    ],
                }
            ],
        }
    ]

    items = list_report_menu_items(menu_list)
    lookup = build_menu_lookup(menu_list)

    assert len(items) == 1
    assert items[0]["FuncName"] == "库存明细统计"
    assert lookup["库存明细统计"]["FuncUrl"] == "StockList"


def test_list_menu_items_supports_non_report_root_and_variant_alias_lookup():
    menu_list = [
        {
            "FuncName": "会员资料",
            "FuncLID": "E002",
            "SubList": [
                {
                    "FuncName": "会员中心",
                    "FuncLID": "E002001",
                    "FuncUrl": "MemberCenter",
                }
            ],
        },
        {
            "FuncName": "报表管理",
            "FuncLID": "E004",
            "SubList": [
                {
                    "FuncName": "库存报表",
                    "FuncLID": "E004002",
                    "SubList": [
                        {
                            "FuncName": "库存综合分析",
                            "FuncLID": "E004002003",
                            "FuncUrl": "StockAnalysis",
                        }
                    ],
                }
            ],
        },
    ]

    items = list_menu_items(menu_list)
    lookup = build_menu_lookup(menu_list)

    assert len(items) == 2
    assert lookup["会员资料::会员中心"]["FuncUrl"] == "MemberCenter"
    assert lookup["报表管理::库存综合分析-按中分类"]["FuncUrl"] == "StockAnalysis"
    assert lookup["会员中心"]["FuncUrl"] == "MemberCenter"


def test_build_page_scope_texts_deduplicates_variant_targets(tmp_path: Path):
    report_doc = tmp_path / "report_api_samples.md"
    report_doc.write_text("", "utf-8")
    api_images_dir = tmp_path / "images"
    api_images_dir.mkdir()
    (api_images_dir / "库存综合分析-按中分类-1.png").write_bytes(b"fake")

    registry = build_page_research_registry(report_doc, api_images_dir)
    entry = next(item for item in registry if item.title == "库存综合分析-按中分类")

    assert build_page_scope_texts(entry) == ("库存综合分析-按中分类", "库存综合分析")


def test_build_page_scope_action_texts_collects_recipe_targets(tmp_path: Path):
    report_doc = tmp_path / "report_api_samples.md"
    report_doc.write_text("", "utf-8")
    api_images_dir = tmp_path / "images"
    api_images_dir.mkdir()
    (api_images_dir / "收货确认-1.png").write_bytes(b"fake")

    registry = build_page_research_registry(report_doc, api_images_dir)
    entry = next(item for item in registry if item.title == "收货确认")

    assert build_page_scope_action_texts(entry) == ("单据确认", "物流信息")


def test_diff_payload_paths_reports_nested_changes():
    before = {
        "parameter": {
            "BeginDate": "20250301",
            "EndDate": "20260401",
            "Tiem": "0",
        }
    }
    after = {
        "parameter": {
            "BeginDate": "20250301",
            "EndDate": "20260401",
            "Tiem": "1",
        }
    }

    diff = diff_payload_paths(before, after)

    assert diff["changed_count"] == 1
    assert diff["changed_paths"][0]["path"] == "parameter.Tiem"
    assert diff["changed_paths"][0]["before"] == "0"
    assert diff["changed_paths"][0]["after"] == "1"


def test_build_page_manifest_summary_detects_sales_multi_grain_route():
    manifest = {
        "page": {"title": "销售清单"},
        "status": "ok",
        "visible_controls": [{"text": "按单据"}, {"text": "按明细"}],
        "network": {
            "requests": [
                {
                    "id": 1,
                    "url": "https://jyapistaging.yeusoft.net/JyApi/Grid/GetViewGridList",
                    "post_data": {"menuid": "E004001008", "gridid": "E004001008_1", "isJyApi": True},
                },
                {
                    "id": 2,
                    "url": "https://erpapistaging.yeusoft.net/FxErpApi/FXDIYReport/GetDIYReportData",
                    "post_data": {
                        "menuid": "E004001008",
                        "gridid": "E004001008_2",
                        "parameter": {"BeginDate": "20250301", "EndDate": "20260401", "Tiem": "1"},
                    },
                },
                {
                    "id": 3,
                    "url": "https://erpapistaging.yeusoft.net/eposapi/YisEposReport/SelSaleReport",
                    "post_data": {"page": 1, "pagesize": 999999, "bdate": "20250301", "edate": "20260401"},
                },
            ],
            "responses": [
                {
                    "request_id": 1,
                    "url": "https://jyapistaging.yeusoft.net/JyApi/Grid/GetViewGridList",
                    "response_summary": {
                        "row_count": 0,
                        "response_shape": "Data[].ViewList",
                    },
                },
                {
                    "request_id": 2,
                    "url": "https://erpapistaging.yeusoft.net/FxErpApi/FXDIYReport/GetDIYReportData",
                    "response_summary": {
                        "row_count": 9839,
                        "response_shape": "retdata[]",
                        "columns_signature": "detail",
                        "row_set_signature": "detail-set",
                    },
                },
                {
                    "request_id": 3,
                    "url": "https://erpapistaging.yeusoft.net/eposapi/YisEposReport/SelSaleReport",
                    "response_summary": {
                        "row_count": 3714,
                        "response_shape": "retdata.Data",
                        "columns_signature": "header",
                        "row_set_signature": "header-set",
                    },
                },
            ],
        },
    }

    summary = build_page_manifest_summary(manifest)

    assert summary["grain_route"] == "multi_grain_route"
    assert summary["recommended_capture_strategy"] == "split_head_and_line_routes"
    assert summary["candidate_join_keys"] == ["sale_no", "sale_date", "operator", "vip_card_no"]
    assert "SelSaleReport" in summary["source_candidates"]
    assert "GetDIYReportData" in summary["source_candidates"]


def test_build_single_variable_probe_cases_for_sales_menu_include_head_and_line_routes(tmp_path: Path):
    report_doc = tmp_path / "report_api_samples.md"
    report_doc.write_text(
        """
### 销售清单
```bash
curl 'https://example.com/FxErpApi/FXDIYReport/GetDIYReportData' --data-raw '{"menuid":"E004001008","gridid":"E004001008_2","parameter":{"BeginDate":"20250301","EndDate":"20260401","Depart":"A0190248","Tiem":"1"}}'
```
""".strip(),
        "utf-8",
    )
    registry = build_page_research_registry(report_doc, tmp_path / "images")
    entry = next(item for item in registry if item.title == "销售清单")

    probes = build_single_variable_probe_cases(entry)
    labels = {probe.label for probe in probes}

    assert "单变量探测：销售清单按单据路线" in labels
    assert "单变量探测：销售清单按明细路线" in labels
    assert any(probe.parameter_path == "parameter.Tiem" and probe.parameter_value == "0" for probe in probes)
    assert any(probe.parameter_path == "parameter.Depart" for probe in probes)


def test_build_page_manifest_summary_includes_probe_semantics():
    manifest = {
        "page": {"title": "库存明细统计"},
        "status": "ok",
        "visible_controls": [],
        "actions": [
            {
                "key": "query",
                "label": "执行查询",
                "response_fingerprints": [
                    {
                        "endpoint": "SelDeptStockWaitList",
                        "row_count": 975,
                        "columns_signature": "columns-a",
                        "row_set_signature": "rows-a",
                        "is_data_endpoint": True,
                    }
                ],
            },
            {
                "key": "probe_stockflag_0",
                "label": "单变量探测：库存明细统计 stockflag=0",
                "probe": {
                    "parameter_path": "stockflag",
                    "parameter_value": "0",
                    "category": "enum",
                },
                "request_diffs": [{"path": "stockflag", "before": "0", "after": "0"}],
                "response_fingerprints": [
                    {
                        "endpoint": "SelDeptStockWaitList",
                        "row_count": 975,
                        "columns_signature": "columns-a",
                        "row_set_signature": "rows-a",
                        "is_data_endpoint": True,
                    }
                ],
            },
            {
                "key": "probe_stockflag_1",
                "label": "单变量探测：库存明细统计 stockflag=1",
                "probe": {
                    "parameter_path": "stockflag",
                    "parameter_value": "1",
                    "category": "enum",
                },
                "request_diffs": [{"path": "stockflag", "before": "0", "after": "1"}],
                "response_fingerprints": [
                    {
                        "endpoint": "SelDeptStockWaitList",
                        "row_count": 1548,
                        "columns_signature": "columns-a",
                        "row_set_signature": "rows-b",
                        "is_data_endpoint": True,
                    }
                ],
            },
        ],
        "network": {"requests": [], "responses": []},
    }

    summary = build_page_manifest_summary(manifest)

    assert summary["baseline_request_signature"][0]["endpoint"] == "SelDeptStockWaitList"
    assert len(summary["single_variable_probe_results"]) == 2
    assert summary["parameter_semantics"]["stockflag"]["semantics"] == "data_subset_or_scope_switch"
    assert summary["parameter_semantics"]["stockflag"]["recommended_http_strategy"] == "枚举 sweep"


def test_build_page_manifest_summary_keeps_variant_metadata():
    manifest = {
        "page": {
            "title": "库存综合分析-按中分类",
            "menu_target_title": "库存综合分析",
            "menu_root_name": "报表管理",
            "variant_label": "按中分类",
            "variant_of": "库存综合分析",
        },
        "status": "ok",
        "visible_controls": [],
        "network": {"requests": [], "responses": []},
    }

    summary = build_page_manifest_summary(manifest)

    assert summary["title"] == "库存综合分析-按中分类"
    assert summary["menu_target_title"] == "库存综合分析"
    assert summary["menu_root_name"] == "报表管理"
    assert summary["variant_label"] == "按中分类"
    assert summary["variant_of"] == "库存综合分析"


def test_build_page_manifest_summary_detects_return_detail_data_endpoint():
    manifest = {
        "page": {"title": "退货明细"},
        "status": "ok",
        "visible_controls": [],
        "network": {
            "requests": [
                {
                    "id": 1,
                    "url": "https://jyapistaging.yeusoft.net/JyApi/Grid/GetViewGridList",
                    "post_data": {"menuid": "E004003004", "gridid": "E004003004_2", "isJyApi": True},
                },
                {
                    "id": 2,
                    "url": "https://erpapistaging.yeusoft.net/eposapi/YisEposReport/ReturnStockBaseInfo",
                    "post_data": {"menuid": "E004003004"},
                },
                {
                    "id": 3,
                    "url": "https://erpapistaging.yeusoft.net/eposapi/YisEposReport/SelReturnStockList",
                    "post_data": {
                        "menuid": "E004003004",
                        "gridid": "E004003004_2",
                        "warecause": "",
                        "spenum": "",
                        "type": "0",
                    },
                },
            ],
            "responses": [
                {
                    "request_id": 1,
                    "url": "https://jyapistaging.yeusoft.net/JyApi/Grid/GetViewGridList",
                    "response_summary": {"row_count": 0, "response_shape": "Data[].ViewList"},
                },
                {
                    "request_id": 2,
                    "url": "https://erpapistaging.yeusoft.net/eposapi/YisEposReport/ReturnStockBaseInfo",
                    "response_summary": {"row_count": 0, "response_shape": "retdata"},
                },
                {
                    "request_id": 3,
                    "url": "https://erpapistaging.yeusoft.net/eposapi/YisEposReport/SelReturnStockList",
                    "response_summary": {
                        "row_count": 42,
                        "response_shape": "retdata.Data",
                        "columns_signature": "return-columns",
                        "row_set_signature": "return-set",
                    },
                },
            ],
        },
    }

    summary = build_page_manifest_summary(manifest)

    assert summary["source_candidates"] == ["SelReturnStockList"]
    assert "GetViewGridList" in summary["result_snapshot_candidates"]
    assert "ReturnStockBaseInfo" in summary["result_snapshot_candidates"]


def test_summarize_page_manifests_reports_failed_pages():
    manifests = [
        {
            "page": {
                "title": "销售清单",
                "menu_target_title": "销售清单",
                "menu_root_name": "报表管理",
                "variant_label": None,
                "variant_of": None,
            },
            "status": "ok",
            "visible_controls": [],
            "network": {"requests": [], "responses": []},
        },
        {
            "page": {
                "title": "库存明细统计",
                "menu_target_title": "库存明细统计",
                "menu_root_name": "报表管理",
                "variant_label": None,
                "variant_of": None,
            },
            "status": "failed",
            "error": "menu missing",
            "visible_controls": [],
            "network": {"requests": [], "responses": []},
        },
    ]

    summary = summarize_page_manifests(manifests)

    assert summary["page_count"] == 2
    assert summary["success_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["failed_pages"][0]["title"] == "库存明细统计"
    assert summary["pages"][0]["title"] == "销售清单"
    assert summary["pages"][0]["menu_target_title"] == "销售清单"
    assert summary["pages"][0]["menu_root_name"] == "报表管理"
    assert summary["pages"][0]["summary"]["title"] == "销售清单"


def test_get_probe_target_titles_returns_sales_inventory_pages():
    titles = get_probe_target_titles("sales_inventory")

    assert "销售清单" in titles
    assert "库存明细统计" in titles
    assert "出入库单据" in titles
