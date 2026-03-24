from __future__ import annotations

import json
from pathlib import Path

import scripts.build_erp_api_maturity_board as board_script
import scripts.build_erp_capture_route_registry as registry_script
from app.services.capture.route_registry import build_capture_route_registry_from_board
from app.services.research.maturity_board import build_api_maturity_board


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, "utf-8")


def _ledger(rows: list[tuple[str, str, str, str, str]]) -> str:
    body = "\n".join(
        f"| {title} | `{endpoint}` | `POST` | `token` | `page` `pagesize` | {current_judgment} | {risk} | {strategy} |"
        for title, endpoint, current_judgment, risk, strategy in rows
    )
    return f"""# 台账

## 2. 接口总表

| 页面/报表 | endpoint | method | 认证方式 | 主要过滤字段 | 当前判断 | 风险标签 | 抓取策略 |
| --- | --- | --- | --- | --- | --- | --- | --- |
{body}
"""


def _build_fixture_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"

    _write(
        repo_root / "docs" / "erp" / "sales-ledger.md",
        _ledger(
            [
                ("销售清单", "FXDIYReport/GetDIYReportData", "当前最接近销售明细源", "需要扫枚举", "单请求"),
                ("零售明细统计", "YisEposReport/SelDeptSaleList", "更像销售明细结果接口，可作为销售域候选源", "需要翻页", "自动翻页"),
            ]
        ),
    )
    _write(
        repo_root / "docs" / "erp" / "inventory-ledger.md",
        _ledger(
            [
                ("库存明细统计", "YisEposReport/SelDeptStockWaitList", "当前最像库存事实源候选", "需要翻页", "自动翻页"),
                ("出入库单据", "YisEposReport/SelOutInStockReport", "准明细单据源候选", "需要扫枚举", "自动翻页"),
            ]
        ),
    )
    _write(repo_root / "docs" / "erp" / "member-ledger.md", _ledger([]))
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", _ledger([]))
    _write(repo_root / "docs" / "erp" / "payment-and-doc-ledger.md", _ledger([]))

    report_matrix = [
        {"title": "销售清单"},
        {"title": "零售明细统计"},
        {"title": "库存明细统计"},
        {"title": "出入库单据"},
    ]
    _write(analysis_root / "report-matrix-20260322-000000.json", json.dumps(report_matrix, ensure_ascii=False))

    page_research = {
        "pages": [
            {
                "title": "销售清单",
                "status": "ok",
                "grain_route": "multi_grain_route",
                "endpoint_summaries": [{"endpoint": "SelSaleReport"}],
                "single_variable_probe_results": [{"action_key": "probe_tiem"}],
                "payload_hints": {"pagination_fields": [], "enum_fields": ["Tiem"]},
            },
            {
                "title": "零售明细统计",
                "status": "ok",
                "grain_route": "enum_or_scope_route",
                "endpoint_summaries": [{"endpoint": "SelDeptSaleList"}],
                "single_variable_probe_results": [{"action_key": "probe_page"}],
                "payload_hints": {"pagination_fields": ["page"], "enum_fields": []},
            },
            {
                "title": "库存明细统计",
                "status": "ok",
                "grain_route": "enum_or_scope_route",
                "endpoint_summaries": [{"endpoint": "SelDeptStockWaitList"}],
                "single_variable_probe_results": [{"action_key": "probe_stockflag"}],
                "payload_hints": {"pagination_fields": ["page"], "enum_fields": ["stockflag"]},
            },
            {
                "title": "出入库单据",
                "status": "ok",
                "grain_route": "enum_or_scope_route",
                "endpoint_summaries": [{"endpoint": "SelOutInStockReport"}],
                "single_variable_probe_results": [{"action_key": "probe_datetype"}],
                "payload_hints": {"pagination_fields": ["page"], "enum_fields": ["datetype", "type", "doctype"]},
            },
        ]
    }
    _write(analysis_root / "yeusoft-page-research-20260322-000100.json", json.dumps(page_research, ensure_ascii=False))

    sales_evidence = {
        "issue_flags": [],
        "join_key_analysis": {
            "candidate_keys": [
                {"key": "sale_no", "stable_candidate": True},
                {"key": "sale_date", "stable_candidate": False},
                {"key": "operator", "stable_candidate": False},
                {"key": "vip_card_no", "stable_candidate": True},
            ]
        },
        "detail_only_sale_no_profile": {
            "detail_only_sale_no_count": 12,
            "detail_only_row_count": 34,
        },
        "capture_admission": {
            "head_document_uniqueness": {"head_document_uniqueness_ok": True},
            "reverse_split_ready": True,
            "capture_admission_ready": True,
            "reverse_route_blocking_issues": [],
        },
    }
    _write(analysis_root / "sales-evidence-chain-20260322-000200.json", json.dumps(sales_evidence, ensure_ascii=False))

    inventory_evidence = {
        "inventory_detail": {
            "parameter_semantics": {
                "stockflag": {
                    "semantics": "data_subset_or_scope_switch",
                    "variants": [{"value": "0"}, {"value": "1"}, {"value": "2"}],
                },
                "page": {
                    "semantics": "same_dataset",
                    "interpretation": {
                        "kind": "page_ignored_in_http_or_first_page_is_full",
                        "note": "纯 HTTP 下 page=0/1 返回同一数据集。",
                    },
                },
            },
            "stockflag_equivalence": {"stockflag_1_equals_2": True},
        },
        "outin_report": {
            "parameter_semantics": {
                "datetype": {
                    "semantics": "data_subset_or_scope_switch",
                    "variants": [{"value": "1"}, {"value": "2"}],
                },
                "type": {"semantics": "data_subset_or_scope_switch"},
                "doctype": {"semantics": "data_subset_or_scope_switch"},
            },
            "type_sweep_summary": {"recommended_distinct_values": ["已出库", "已入库", "在途"]},
            "doctype_sweep_summary": {
                "recommended_distinct_values": ["1", "2", "3", "7"],
                "equivalent_value_groups": [["3", "4", "5", "6"]],
            },
        },
    }
    _write(analysis_root / "inventory-evidence-chain-20260322-000250.json", json.dumps(inventory_evidence, ensure_ascii=False))

    inventory_outin_research = {
        "summary": {
            "outin_report": {
                "research_sweep_summary": {
                    "minimum_sweep_complete": True,
                    "doctype_schema_stable": True,
                    "active_doctype_values": ["1", "2", "7"],
                    "placeholder_only_doctype_values": ["3"],
                }
            }
        }
    }
    _write(
        analysis_root / "inventory-outin-capture-research-20260322-000260.json",
        json.dumps(inventory_outin_research, ensure_ascii=False),
    )

    menu_coverage = {
        "summary": {
            "audit_complete": True,
            "all_visible_pages_classified": True,
            "menu_node_count": 8,
            "container_only_count": 0,
            "clickable_page_count": 4,
            "covered_count": 4,
            "visible_but_untracked_count": 0,
            "visible_but_failed_count": 0,
            "unknown_pages": [],
            "unmatched_registry_targets": [],
        },
        "pages": [
            {
                "title": "销售清单",
                "page_title": "销售清单",
                "menu_path": ["报表管理", "零售报表", "销售清单"],
                "root_name": "报表管理",
                "group_name": "零售报表",
                "coverage_status": "covered",
                "coverage_confidence": "high",
                "matched_registry_titles": ["销售清单"],
            },
            {
                "title": "零售明细统计",
                "page_title": "零售明细统计",
                "menu_path": ["报表管理", "零售报表", "零售明细统计"],
                "root_name": "报表管理",
                "group_name": "零售报表",
                "coverage_status": "covered",
                "coverage_confidence": "high",
                "matched_registry_titles": ["零售明细统计"],
            },
            {
                "title": "库存明细统计",
                "page_title": "库存明细统计",
                "menu_path": ["报表管理", "库存报表", "库存明细统计"],
                "root_name": "报表管理",
                "group_name": "库存报表",
                "coverage_status": "covered",
                "coverage_confidence": "high",
                "matched_registry_titles": ["库存明细统计"],
            },
            {
                "title": "出入库单据",
                "page_title": "出入库单据",
                "menu_path": ["报表管理", "库存报表", "出入库单据"],
                "root_name": "报表管理",
                "group_name": "库存报表",
                "coverage_status": "covered",
                "coverage_confidence": "high",
                "matched_registry_titles": ["出入库单据"],
            },
        ],
        "containers": [],
    }
    _write(analysis_root / "menu-coverage-audit-20260322-000300.json", json.dumps(menu_coverage, ensure_ascii=False))

    return repo_root, analysis_root


def test_board_and_registry_keep_capture_ready_routes_consistent(tmp_path: Path) -> None:
    repo_root, analysis_root = _build_fixture_repo(tmp_path)

    board = build_api_maturity_board(repo_root, analysis_root)
    registry = build_capture_route_registry_from_board(board)

    board_routes = {entry["route"]: entry for entry in board["entries"]}
    registry_routes = {entry["route"]: entry for entry in registry["routes"]}

    assert set(board_routes) == set(registry_routes)
    assert registry["summary"]["ready_for_capture_admission_count"] == sum(
        1 for item in registry_routes.values() if item["capture_status"] == "ready_for_capture_admission"
    )
    assert registry["summary"]["confirmed_capture_route_count"] == sum(
        1 for item in registry_routes.values() if item["capture_route_confirmed"]
    )

    ready_routes = {
        route
        for route, item in registry_routes.items()
        if item["capture_status"] == "ready_for_capture_admission"
    }
    assert ready_routes == {
        "SelSaleReport",
        "GetDIYReportData(E004001008_2)",
        "库存明细统计 / SelDeptStockWaitList",
        "出入库单据 / SelOutInStockReport",
    }
    assert board_routes["SelSaleReport"]["capture_admission_ready"] is True
    assert board_routes["GetDIYReportData(E004001008_2)"]["capture_admission_ready"] is True
    assert board_routes["库存明细统计 / SelDeptStockWaitList"]["capture_admission_ready"] is True
    assert board_routes["出入库单据 / SelOutInStockReport"]["capture_admission_ready"] is True
    assert registry_routes["SelDeptSaleList"]["capture_status"] == "reconciliation_only"
    assert registry_routes["sales_reverse_document_lines"]["capture_status"] == "research_capture_only"
    assert registry_routes["出入库单据 / SelOutInStockReport"]["capture_parameter_plan"] == {
        "datetype_values": ["1", "2"],
        "type_values": ["已出库", "已入库", "在途"],
        "doctype_values": ["1", "2", "7"],
        "validated_minimum_sweep": True,
    }


def test_build_erp_api_maturity_board_script_smoke(tmp_path: Path, monkeypatch) -> None:
    repo_root, analysis_root = _build_fixture_repo(tmp_path)
    output_doc = tmp_path / "api-maturity-board.md"
    output_json = tmp_path / "api-maturity-board.json"

    monkeypatch.setattr(board_script, "PROJECT_ROOT", repo_root)
    monkeypatch.setattr(
        board_script.sys,
        "argv",
        [
            "build_erp_api_maturity_board.py",
            "--analysis-root",
            str(analysis_root),
            "--board-doc",
            str(output_doc),
            "--board-json",
            str(output_json),
        ],
    )

    assert board_script.main() == 0
    assert output_doc.exists()
    assert output_json.exists()

    payload = json.loads(output_json.read_text("utf-8"))
    markdown = output_doc.read_text("utf-8")
    assert payload["summary"]["global_risk_map_complete"] is True
    assert payload["summary"]["total_routes"] == 6
    assert "# ERP API 成熟度总览" in markdown
    assert "SelSaleReport" in markdown
    assert "当前账号可见菜单覆盖审计完成" in markdown


def test_build_erp_capture_route_registry_script_smoke(tmp_path: Path, monkeypatch) -> None:
    repo_root, analysis_root = _build_fixture_repo(tmp_path)
    output_doc = tmp_path / "capture-route-registry.md"
    output_json = tmp_path / "capture-route-registry.json"

    monkeypatch.setattr(registry_script, "PROJECT_ROOT", repo_root)
    monkeypatch.setattr(
        registry_script.sys,
        "argv",
        [
            "build_erp_capture_route_registry.py",
            "--analysis-root",
            str(analysis_root),
            "--registry-doc",
            str(output_doc),
            "--registry-json",
            str(output_json),
        ],
    )

    assert registry_script.main() == 0
    assert output_doc.exists()
    assert output_json.exists()

    payload = json.loads(output_json.read_text("utf-8"))
    markdown = output_doc.read_text("utf-8")
    routes = {item["route"]: item for item in payload["routes"]}
    assert payload["summary"]["ready_for_capture_admission_count"] == 4
    assert routes["SelSaleReport"]["capture_route_name"] == "sales_documents_head"
    assert routes["出入库单据 / SelOutInStockReport"]["capture_route_name"] == "inventory_inout_documents"
    assert routes["出入库单据 / SelOutInStockReport"]["capture_status"] == "ready_for_capture_admission"
    assert "# ERP Capture 路线注册表" in markdown
    assert "inventory_inout_documents" in markdown
    assert "可准入 capture" in markdown
