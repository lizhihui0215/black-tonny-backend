from __future__ import annotations

import json
from pathlib import Path

from app.services.research.maturity_board import (
    build_api_maturity_board,
    render_api_maturity_board_markdown,
    resolve_page_research_record,
)


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


def test_resolve_page_research_record_supports_aliases():
    records = {"会员消费排行榜": {"title": "会员消费排行榜", "status": "ok"}}

    resolved = resolve_page_research_record("会员消费排行", records)

    assert resolved is not None
    assert resolved["title"] == "会员消费排行榜"


def test_build_api_maturity_board_splits_sales_routes_and_marks_inventory_followups(tmp_path: Path):
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
    _write(
        repo_root / "docs" / "erp" / "member-ledger.md",
        _ledger([("会员中心", "YisEposVipManage/SelVipInfoList", "当前最像会员主数据查询接口", "大概率全量", "单请求")]),
    )
    _write(
        repo_root / "docs" / "erp" / "stored-value-ledger.md",
        _ledger([("储值卡明细", "FXDIYReport/GetDIYReportData", "当前最像储值流水明细候选", "需要扫枚举", "单请求")]),
    )
    _write(
        repo_root / "docs" / "erp" / "payment-and-doc-ledger.md",
        _ledger([("每日流水单", "JyApi/ReconciliationAnalysis/SelectRetailDocPaymentSlip", "支付流水结果接口，高价值但需继续摸清查询语义", "需要扫枚举", "结果快照")]),
    )

    report_matrix = [
        {"title": "销售清单"},
        {"title": "零售明细统计"},
        {"title": "库存明细统计"},
        {"title": "出入库单据"},
        {"title": "会员中心"},
        {"title": "储值卡明细"},
        {"title": "每日流水单"},
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
            },
            {
                "title": "零售明细统计",
                "status": "ok",
                "grain_route": "enum_or_scope_route",
                "endpoint_summaries": [{"endpoint": "SelDeptSaleList"}],
                "single_variable_probe_results": [{"action_key": "probe_page"}],
            },
            {
                "title": "库存明细统计",
                "status": "ok",
                "grain_route": "enum_or_scope_route",
                "endpoint_summaries": [{"endpoint": "SelDeptStockWaitList"}],
                "single_variable_probe_results": [{"action_key": "probe_stockflag"}],
            },
            {
                "title": "出入库单据",
                "status": "ok",
                "grain_route": "enum_or_scope_route",
                "endpoint_summaries": [{"endpoint": "SelOutInStockReport"}],
                "single_variable_probe_results": [{"action_key": "probe_datetype"}],
            },
            {
                "title": "会员中心",
                "status": "ok",
                "grain_route": "single_route",
                "endpoint_summaries": [{"endpoint": "SelVipInfoList"}],
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
            "head_document_uniqueness": {
                "head_document_uniqueness_ok": True,
            },
            "reverse_split_ready": True,
            "capture_admission_ready": True,
            "reverse_route_blocking_issues": [],
        },
    }
    _write(analysis_root / "sales-evidence-chain-20260322-000200.json", json.dumps(sales_evidence, ensure_ascii=False))
    _write(
        analysis_root / "sales-capture-admission-20260322-000205.json",
        json.dumps({"capture_batch_id": "sales-batch-001"}, ensure_ascii=False),
    )
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
            "stockflag_equivalence": {
                "stockflag_1_equals_2": True,
            },
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
            "type_sweep_summary": {
                "recommended_distinct_values": ["已出库", "已入库", "在途"],
            },
            "doctype_sweep_summary": {
                "recommended_distinct_values": ["1", "2", "3", "7"],
                "equivalent_value_groups": [["3", "4", "5", "6"]],
            },
        },
    }
    _write(analysis_root / "inventory-evidence-chain-20260322-000250.json", json.dumps(inventory_evidence, ensure_ascii=False))
    _write(
        analysis_root / "inventory-stock-capture-admission-20260322-000255.json",
        json.dumps({"capture_batch_id": "inventory-stock-batch-001"}, ensure_ascii=False),
    )
    member_evidence = {
        "member_center": {
            "capture_admission_ready": True,
            "blocking_issues": [],
            "declared_total_count": 1309,
            "full_capture_with_default_query": True,
            "parameter_semantics": {
                "searchval": {"semantics": "data_subset_or_scope_switch", "variants": [{"value": "exact_search"}]},
                "VolumeNumber": {"semantics": "data_subset_or_scope_switch", "variants": [{"value": "1"}]},
            },
            "search_behavior": {
                "exact_match_values": ["exact_search"],
            },
            "condition_probe_summary": {
                "invalid_condition_values": ["name", "VipCode"],
            },
            "follow_up_issues": [
                "condition 语义仍待确认",
                "VolumeNumber 的业务语义仍待命名",
            ],
        }
    }
    _write(analysis_root / "member-evidence-chain-20260322-000260.json", json.dumps(member_evidence, ensure_ascii=False))
    _write(
        analysis_root / "member-capture-research-20260322-000262.json",
        json.dumps({"capture_batch_id": "member-batch-001"}, ensure_ascii=False),
    )
    _write(
        analysis_root / "member-capture-admission-20260323-000001.json",
        json.dumps({"capture_batch_id": "member-admit-001"}, ensure_ascii=False),
    )
    _write(
        analysis_root / "inventory-outin-capture-admission-20260322-000265.json",
        json.dumps({"capture_batch_id": "inventory-outin-batch-001"}, ensure_ascii=False),
    )
    menu_coverage = {
        "summary": {
            "audit_complete": True,
            "all_visible_pages_classified": True,
            "menu_node_count": 9,
            "container_only_count": 2,
            "clickable_page_count": 6,
            "covered_count": 5,
            "visible_but_untracked_count": 1,
            "visible_but_failed_count": 0,
            "unknown_pages": [
                {
                    "title": "未知销售页面",
                    "menu_path": ["报表管理", "零售报表", "未知销售页面"],
                    "root_name": "报表管理",
                    "group_name": "零售报表",
                }
            ],
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
            {
                "title": "会员中心",
                "page_title": "会员中心",
                "menu_path": ["会员资料", "会员中心"],
                "root_name": "会员资料",
                "group_name": "",
                "coverage_status": "covered",
                "coverage_confidence": "high",
                "matched_registry_titles": ["会员中心"],
            },
            {
                "title": "储值卡明细",
                "page_title": "储值卡明细",
                "menu_path": ["报表管理", "会员报表", "储值卡明细"],
                "root_name": "报表管理",
                "group_name": "会员报表",
                "coverage_status": "covered",
                "coverage_confidence": "high",
                "matched_registry_titles": ["储值卡明细"],
            },
            {
                "title": "未知销售页面",
                "page_title": "未知销售页面",
                "menu_path": ["报表管理", "零售报表", "未知销售页面"],
                "root_name": "报表管理",
                "group_name": "零售报表",
                "coverage_status": "visible_but_untracked",
                "coverage_confidence": "medium",
                "matched_registry_titles": [],
            },
        ],
        "containers": [],
    }
    _write(analysis_root / "menu-coverage-audit-20260322-000300.json", json.dumps(menu_coverage, ensure_ascii=False))

    board = build_api_maturity_board(repo_root, analysis_root)

    routes = {entry["route"]: entry for entry in board["entries"]}
    assert "SelSaleReport" in routes
    assert "GetDIYReportData(E004001008_2)" in routes
    assert routes["SelSaleReport"]["source_kind"] == "主源候选"
    assert routes["SelSaleReport"]["research_map_complete"] is True
    assert routes["SelSaleReport"]["reliability_status"] == "中等可信"
    assert routes["SelSaleReport"]["menu_path"] == ["报表管理", "零售报表", "销售清单"]
    assert routes["SelSaleReport"]["coverage_status"] == "covered"
    assert routes["SelSaleReport"]["blocking_issues"] == []
    assert routes["SelSaleReport"]["capture_admission_ready"] is True
    assert routes["SelSaleReport"]["capture_written_once"] is True
    assert routes["SelSaleReport"]["latest_capture_batch_id"] == "sales-batch-001"
    assert routes["GetDIYReportData(E004001008_2)"]["blocking_issues"] == []
    assert routes["GetDIYReportData(E004001008_2)"]["reverse_split_ready"] is True
    assert routes["GetDIYReportData(E004001008_2)"]["capture_written_once"] is True
    assert "sales_reverse_document_lines" in routes
    assert routes["sales_reverse_document_lines"]["source_kind"] == "研究留痕"
    assert routes["sales_reverse_document_lines"]["capture_written_once"] is True
    assert routes["SelDeptSaleList"]["role"] == "对账源"
    assert routes["SelDeptSaleList"]["blocking_issues"] == []
    assert routes["库存明细统计 / SelDeptStockWaitList"]["stage"] == "已HTTP回证"
    assert routes["库存明细统计 / SelDeptStockWaitList"]["capture_admission_ready"] is True
    assert routes["库存明细统计 / SelDeptStockWaitList"]["capture_written_once"] is True
    assert routes["库存明细统计 / SelDeptStockWaitList"]["latest_capture_batch_id"] == "inventory-stock-batch-001"
    assert routes["库存明细统计 / SelDeptStockWaitList"]["capture_parameter_plan"] == {
        "stockflag_values": ["0", "1"],
        "page_mode": "fixed_page_zero",
    }
    assert routes["库存明细统计 / SelDeptStockWaitList"]["blocking_issues"] == []
    assert routes["库存明细统计 / SelDeptStockWaitList"]["next_action"] == "已进入 capture admit；继续观测批次回归指标，并在 serving 继续冻结的前提下推进下一条路线。"
    assert routes["出入库单据 / SelOutInStockReport"]["stage"] == "已HTTP回证"
    assert routes["出入库单据 / SelOutInStockReport"]["capture_admission_ready"] is False
    assert routes["出入库单据 / SelOutInStockReport"]["recommended_doctype_values"] == ["1", "2", "3", "7"]
    assert routes["出入库单据 / SelOutInStockReport"]["capture_written_once"] is True
    assert routes["出入库单据 / SelOutInStockReport"]["latest_capture_batch_id"] == "inventory-outin-batch-001"
    assert routes["会员中心 / SelVipInfoList"]["stage"] == "已HTTP回证"
    assert routes["会员中心 / SelVipInfoList"]["capture_admission_ready"] is True
    assert routes["会员中心 / SelVipInfoList"]["blocking_issues"] == []
    assert routes["会员中心 / SelVipInfoList"]["capture_parameter_plan"]["default_condition"] == ""
    assert routes["会员中心 / SelVipInfoList"]["capture_written_once"] is True
    assert routes["会员中心 / SelVipInfoList"]["latest_capture_batch_id"] == "member-admit-001"
    assert routes["会员中心 / SelVipInfoList"]["latest_capture_mode"] == "admission"
    assert "未知销售页面 / unknown_page_needs_baseline" in routes
    assert routes["未知销售页面 / unknown_page_needs_baseline"]["source_kind"] == "待识别"
    assert routes["未知销售页面 / unknown_page_needs_baseline"]["coverage_status"] == "visible_but_untracked"
    assert board["summary"]["research_map_complete_count"] == 7
    assert board["summary"]["menu_coverage_audit_complete"] is True
    assert board["summary"]["global_risk_map_complete"] is False
    assert board["summary"]["menu_coverage"]["visible_but_untracked_count"] == 1
    assert board["summary"]["total_routes"] == 10
    assert board["summary"]["capture_written_once_count"] == 6


def test_render_api_maturity_board_markdown_includes_status_sections():
    board = {
        "summary": {
            "total_routes": 1,
            "mainline_ready_count": 0,
            "capture_written_once_count": 1,
            "research_map_complete_count": 1,
            "global_risk_map_complete": True,
            "menu_coverage_audit_complete": True,
            "menu_coverage": {
                "clickable_page_count": 1,
                "covered_count": 1,
                "visible_but_untracked_count": 0,
                "visible_but_failed_count": 0,
                "container_only_count": 0,
                "unmatched_registry_target_count": 0,
                "menu_node_count": 3,
            },
            "stage_counts": {"已HTTP回证": 1},
            "trust_counts": {"中": 1},
            "reliability_counts": {"中等可信": 1},
            "top_blockers": [{"issue": "sale_date 当前不能作为稳定头行关联键", "count": 1}],
            "domains": {
                "sales": {"route_count": 1, "http_verified": 1, "single_variable": 0, "baseline_only": 0, "discovered_only": 0, "high_trust": 0, "medium_trust": 1, "low_trust": 0, "research_map_complete": 1},
                "inventory": {"route_count": 0, "http_verified": 0, "single_variable": 0, "baseline_only": 0, "discovered_only": 0, "high_trust": 0, "medium_trust": 0, "low_trust": 0, "research_map_complete": 0},
                "member": {"route_count": 0, "http_verified": 0, "single_variable": 0, "baseline_only": 0, "discovered_only": 0, "high_trust": 0, "medium_trust": 0, "low_trust": 0, "research_map_complete": 0},
                "stored_value": {"route_count": 0, "http_verified": 0, "single_variable": 0, "baseline_only": 0, "discovered_only": 0, "high_trust": 0, "medium_trust": 0, "low_trust": 0, "research_map_complete": 0},
                "payment_and_docs": {"route_count": 0, "http_verified": 0, "single_variable": 0, "baseline_only": 0, "discovered_only": 0, "high_trust": 0, "medium_trust": 0, "low_trust": 0, "research_map_complete": 0},
            },
        },
        "source_files": {"report_matrix": "tmp/capture-samples/analysis/report-matrix-x.json", "page_research_files": [], "sales_evidence": "tmp/capture-samples/analysis/sales-evidence-chain-x.json", "ledger_files": ["docs/erp/sales-ledger.md"]},
        "admission_gate": ["页面研究已确认接口语义"],
        "entries": [
            {
                "domain": "sales",
                "route": "SelSaleReport",
                "role": "主源候选",
                "source_kind": "主源候选",
                "stage": "已HTTP回证",
                "trust_level": "中",
                "reliability_status": "中等可信",
                "research_map_complete": True,
                "ingestion_blocked_by_global_gate": False,
                "mainline_ready": False,
                "menu_path": ["报表管理", "零售报表", "销售清单"],
                "menu_root_name": "报表管理",
                "page_title": "销售清单",
                "coverage_status": "covered",
                "coverage_confidence": "high",
                "coverage_scope": ["当前账号范围", "多粒度"],
                "blocking_issues": ["sale_date 当前不能作为稳定头行关联键"],
                "next_action": "继续验证 sale_no 头行稳定度",
                "capture_written_once": True,
                "latest_capture_batch_id": "batch-001",
            }
        ],
    }

    markdown = render_api_maturity_board_markdown(board)

    assert "# ERP API 成熟度总览" in markdown
    assert "SelSaleReport" in markdown
    assert "风险地图已完成" in markdown
    assert "全域门槛已达成" in markdown
    assert "当前账号可见菜单覆盖审计完成" in markdown
    assert "覆盖状态" in markdown
    assert "sale_date 当前不能作为稳定头行关联键" in markdown


def test_build_api_maturity_board_promotes_researched_unknown_pages_into_real_routes(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"

    empty_ledger = _ledger([])
    _write(
        repo_root / "docs" / "erp" / "sales-ledger.md",
        _ledger(
            [
                ("商品资料", "YisEposWareList/SelWareList", "当前更像商品主数据页，已确认主接口为 SelWareList", "需要翻页", "自动翻页"),
            ]
        ),
    )
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "member-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "payment-and-doc-ledger.md", empty_ledger)

    page_research = {
        "pages": [
            {
                "title": "商品资料",
                "status": "ok",
                "menu_target_title": "商品资料",
                "menu_root_name": "基础资料",
                "group_name": "",
                "menu_path": ["基础资料", "商品资料"],
                "target_menu_path": ["基础资料", "商品资料"],
                "grain_route": "single_route",
                "endpoint_summaries": [{"endpoint": "SelWareList", "is_data_endpoint": True, "max_row_count": 120}],
                "source_candidates": ["SelWareList"],
                "result_snapshot_candidates": [],
                "recommended_capture_strategy": "baseline_single_request",
                "payload_hints": {"pagination_fields": [], "enum_fields": []},
                "single_variable_probe_results": [],
            },
            {
                "title": "参数设置",
                "status": "ok",
                "menu_target_title": "参数设置",
                "menu_root_name": "其他",
                "group_name": "",
                "menu_path": ["其他", "参数设置"],
                "target_menu_path": ["其他", "参数设置"],
                "grain_route": "single_route",
                "endpoint_summaries": [{"endpoint": "GetViewGridList", "is_data_endpoint": False, "max_row_count": 0}],
                "source_candidates": [],
                "result_snapshot_candidates": ["GetViewGridList"],
                "recommended_capture_strategy": "baseline_single_request",
                "payload_hints": {"pagination_fields": [], "enum_fields": []},
                "single_variable_probe_results": [],
            },
        ]
    }
    _write(analysis_root / "yeusoft-page-research-20260322-000100.json", json.dumps(page_research, ensure_ascii=False))

    menu_coverage = {
        "summary": {
            "audit_complete": True,
            "all_visible_pages_classified": True,
            "menu_node_count": 4,
            "container_only_count": 0,
            "clickable_page_count": 2,
            "covered_count": 2,
            "visible_but_untracked_count": 0,
            "visible_but_failed_count": 0,
            "unknown_pages": [],
            "unmatched_registry_targets": [],
        },
        "pages": [
            {
                "title": "商品资料",
                "page_title": "商品资料",
                "menu_path": ["基础资料", "商品资料"],
                "root_name": "基础资料",
                "group_name": "",
                "coverage_status": "covered",
                "coverage_confidence": "medium",
                "matched_registry_titles": [],
            },
            {
                "title": "参数设置",
                "page_title": "参数设置",
                "menu_path": ["其他", "参数设置"],
                "root_name": "其他",
                "group_name": "",
                "coverage_status": "covered",
                "coverage_confidence": "medium",
                "matched_registry_titles": [],
            },
        ],
        "containers": [],
    }
    _write(analysis_root / "menu-coverage-audit-20260322-000300.json", json.dumps(menu_coverage, ensure_ascii=False))

    board = build_api_maturity_board(repo_root, analysis_root)

    routes = {entry["route"]: entry for entry in board["entries"]}
    assert "商品资料 / SelWareList" in routes
    assert routes["商品资料 / SelWareList"]["source_kind"] == "主源候选"
    assert routes["商品资料 / SelWareList"]["stage"] == "已基线"
    assert routes["商品资料 / SelWareList"]["coverage_status"] == "covered"
    assert routes["参数设置 / GetViewGridList"]["source_kind"] == "未采纳"
    assert routes["参数设置 / GetViewGridList"]["blocking_issues"] == ["配置/设置类页面，默认不进入事实主链"]
    assert board["summary"]["menu_coverage"]["visible_but_untracked_count"] == 0
    assert board["summary"]["global_risk_map_complete"] is True
    assert not any("unknown_page_needs_baseline" in route for route in routes)


def test_build_api_maturity_board_loads_product_capture_runtime_state(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"

    empty_ledger = _ledger([])
    _write(
        repo_root / "docs" / "erp" / "sales-ledger.md",
        _ledger(
            [
                ("商品资料", "YisEposWareList/SelWareList", "当前更像商品主数据页，已确认主接口为 SelWareList", "需要翻页", "自动翻页"),
            ]
        ),
    )
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "member-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "payment-and-doc-ledger.md", empty_ledger)

    page_research = {
        "pages": [
            {
                "title": "商品资料",
                "status": "ok",
                "menu_target_title": "商品资料",
                "menu_root_name": "基础资料",
                "group_name": "",
                "menu_path": ["基础资料", "商品资料"],
                "target_menu_path": ["基础资料", "商品资料"],
                "grain_route": "single_route",
                "endpoint_summaries": [{"endpoint": "SelWareList", "is_data_endpoint": True, "max_row_count": 60}],
                "source_candidates": ["SelWareList"],
                "result_snapshot_candidates": [],
                "recommended_capture_strategy": "http_followup_with_pagination",
                "payload_hints": {"pagination_fields": ["page", "pagesize"], "enum_fields": []},
                "single_variable_probe_results": [],
            },
        ]
    }
    _write(analysis_root / "yeusoft-page-research-20260322-000100.json", json.dumps(page_research, ensure_ascii=False))
    menu_coverage = {
        "summary": {
            "audit_complete": True,
            "all_visible_pages_classified": True,
            "menu_node_count": 2,
            "container_only_count": 0,
            "clickable_page_count": 1,
            "covered_count": 1,
            "visible_but_untracked_count": 0,
            "visible_but_failed_count": 0,
            "unknown_pages": [],
            "unmatched_registry_targets": [],
        },
        "pages": [
            {
                "title": "商品资料",
                "page_title": "商品资料",
                "menu_path": ["基础资料", "商品资料"],
                "root_name": "基础资料",
                "group_name": "",
                "coverage_status": "covered",
                "coverage_confidence": "medium",
                "matched_registry_titles": [],
            }
        ],
        "containers": [],
    }
    _write(analysis_root / "menu-coverage-audit-20260322-000300.json", json.dumps(menu_coverage, ensure_ascii=False))
    _write(
        analysis_root / "product-evidence-chain-20260322-000450.json",
        json.dumps(
            {
                "product_list": {
                    "endpoint": "SelWareList",
                    "blocking_issues": [],
                    "capture_admission_ready": True,
                    "capture_parameter_plan": {
                        "default_spenum": "",
                        "default_warecause": "",
                        "baseline_page": 1,
                        "recommended_pagesize": 5000,
                        "page_mode": "sequential_pagination",
                        "full_capture_with_empty_warecause": True,
                    },
                        "parameter_semantics": {
                            "page": {"semantics": "pagination_page_switch"},
                            "spenum": {"semantics": "scope_or_date_boundary"},
                        },
                    "pagesize_probe_summary": {
                        "tested_page_sizes": [60, 100, 1000, 5000],
                        "recommended_pagesize": 5000,
                        "service_cap_detected": False,
                    },
                    "full_capture_probe_summary": {
                        "declared_total_count": 12125,
                        "observed_total_rows": 12125,
                        "verified_with_empty_warecause": True,
                    },
                    "search_behavior": {
                        "exact_match_values": ["TLX1B90343B"],
                        "broad_match_values": ["TN"],
                        "zero_match_values": [],
                    },
                }
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "product-capture-admission-20260322-000500.json",
        json.dumps(
            {
                "capture_batch_id": "product-batch-001",
                "source_endpoint": "yeusoft.master.product_list",
            },
            ensure_ascii=False,
        ),
    )

    board = build_api_maturity_board(repo_root, analysis_root)
    routes = {entry["route"]: entry for entry in board["entries"]}

    assert routes["商品资料 / SelWareList"]["stage"] == "已HTTP回证"
    assert routes["商品资料 / SelWareList"]["reliability_status"] == "中等可信"
    assert routes["商品资料 / SelWareList"]["capture_admission_ready"] is True
    assert routes["商品资料 / SelWareList"]["capture_parameter_plan"]["recommended_pagesize"] == 5000
    assert routes["商品资料 / SelWareList"]["blocking_issues"] == []
    assert routes["商品资料 / SelWareList"]["mainline_ready"] is True
    assert routes["商品资料 / SelWareList"]["capture_written_once"] is True
    assert routes["商品资料 / SelWareList"]["latest_capture_batch_id"] == "product-batch-001"
    assert routes["商品资料 / SelWareList"]["latest_capture_mode"] == "admission"


def test_build_api_maturity_board_loads_customer_capture_runtime_state(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"

    empty_ledger = _ledger([])
    _write(
        repo_root / "docs" / "erp" / "sales-ledger.md",
        _ledger(
            [
                (
                    "商品资料",
                    "YisEposWareList/SelWareList",
                    "当前更像商品主数据页，已确认主接口为 SelWareList",
                    "需要翻页",
                    "自动翻页",
                )
            ]
        ),
    )
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "member-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "payment-and-doc-ledger.md", empty_ledger)

    page_research = {
        "pages": [
            {
                "title": "客户资料",
                "status": "ok",
                "menu_target_title": "客户资料",
                "menu_root_name": "基础资料",
                "group_name": "",
                "menu_path": ["基础资料", "客户资料"],
                "target_menu_path": ["基础资料", "客户资料"],
                "grain_route": "single_route",
                "endpoint_summaries": [{"endpoint": "SelDeptList", "is_data_endpoint": True, "max_row_count": 0}],
                "source_candidates": ["SelDeptList"],
                "result_snapshot_candidates": [],
                "recommended_capture_strategy": "http_followup_with_pagination",
                "payload_hints": {"pagination_fields": ["page", "pagesize"], "enum_fields": []},
                "single_variable_probe_results": [],
            },
        ]
    }
    _write(analysis_root / "yeusoft-page-research-20260322-000100.json", json.dumps(page_research, ensure_ascii=False))
    menu_coverage = {
        "summary": {
            "audit_complete": True,
            "all_visible_pages_classified": True,
            "menu_node_count": 2,
            "container_only_count": 0,
            "clickable_page_count": 1,
            "covered_count": 1,
            "visible_but_untracked_count": 0,
            "visible_but_failed_count": 0,
            "unknown_pages": [],
            "unmatched_registry_targets": [],
        },
        "pages": [
            {
                "title": "客户资料",
                "page_title": "客户资料",
                "menu_path": ["基础资料", "客户资料"],
                "root_name": "基础资料",
                "group_name": "",
                "coverage_status": "covered",
                "coverage_confidence": "medium",
                "matched_registry_titles": [],
            }
        ],
        "containers": [],
    }
    _write(analysis_root / "menu-coverage-audit-20260322-000300.json", json.dumps(menu_coverage, ensure_ascii=False))
    _write(
        analysis_root / "customer-capture-research-20260322-000500.json",
        json.dumps(
            {
                "capture_batch_id": "customer-batch-001",
                "source_endpoint": "yeusoft.master.customer_list",
            },
            ensure_ascii=False,
        ),
    )

    board = build_api_maturity_board(repo_root, analysis_root)
    routes = {entry["route"]: entry for entry in board["entries"]}

    assert routes["客户资料 / SelDeptList"]["capture_written_once"] is True
    assert routes["客户资料 / SelDeptList"]["latest_capture_batch_id"] == "customer-batch-001"
    assert routes["客户资料 / SelDeptList"]["latest_capture_mode"] == "research"


def test_build_api_maturity_board_tracks_stored_value_evidence_and_runtime(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"

    empty_ledger = _ledger([])
    _write(repo_root / "docs" / "erp" / "sales-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "member-ledger.md", empty_ledger)
    _write(
        repo_root / "docs" / "erp" / "stored-value-ledger.md",
        _ledger([("储值卡明细", "FXDIYReport/GetDIYReportData", "当前最像储值流水明细候选", "需要扫枚举", "单请求")]),
    )
    _write(repo_root / "docs" / "erp" / "payment-and-doc-ledger.md", empty_ledger)

    page_research = {
        "pages": [
            {
                "title": "储值卡明细",
                "status": "ok",
                "menu_target_title": "储值卡明细",
                "menu_root_name": "报表管理",
                "group_name": "会员报表",
                "menu_path": ["报表管理", "会员报表", "储值卡明细"],
                "target_menu_path": ["报表管理", "会员报表", "储值卡明细"],
                "grain_route": "single_route",
                "endpoint_summaries": [{"endpoint": "GetDIYReportData", "is_data_endpoint": True, "max_row_count": 78}],
                "source_candidates": ["GetDIYReportData"],
                "result_snapshot_candidates": [],
                "recommended_capture_strategy": "baseline_single_request",
                "payload_hints": {"pagination_fields": [], "enum_fields": []},
                "single_variable_probe_results": [],
            }
        ]
    }
    _write(analysis_root / "yeusoft-page-research-20260323-000100.json", json.dumps(page_research, ensure_ascii=False))
    menu_coverage = {
        "summary": {
            "audit_complete": True,
            "all_visible_pages_classified": True,
            "menu_node_count": 3,
            "container_only_count": 0,
            "clickable_page_count": 1,
            "covered_count": 1,
            "visible_but_untracked_count": 0,
            "visible_but_failed_count": 0,
            "unknown_pages": [],
            "unmatched_registry_targets": [],
        },
        "pages": [
            {
                "title": "储值卡明细",
                "page_title": "储值卡明细",
                "menu_path": ["报表管理", "会员报表", "储值卡明细"],
                "root_name": "报表管理",
                "group_name": "会员报表",
                "coverage_status": "covered",
                "coverage_confidence": "high",
                "matched_registry_titles": ["储值卡明细"],
            }
        ],
        "containers": [],
    }
    _write(analysis_root / "menu-coverage-audit-20260323-000110.json", json.dumps(menu_coverage, ensure_ascii=False))
    _write(
        analysis_root / "stored-value-evidence-chain-20260323-000120.json",
        json.dumps(
            {
                "stored_value_detail": {
                    "blocking_issues": [],
                    "capture_admission_ready": True,
                    "capture_parameter_plan": {
                        "default_BeginDate": "20250301",
                        "default_EndDate": "20260401",
                        "default_Search": "",
                        "search_mode": "vip_card_only_filter",
                        "page_mode": "single_request_half_open_date_verified",
                        "date_boundary_mode": "half_open_end_date",
                    },
                    "search_behavior": {
                        "supported_search_groups": ["vip_card_id"],
                        "vip_card_filter_confirmed": True,
                        "happen_no_filter_confirmed": False,
                        "vip_name_filter_confirmed": False,
                    },
                    "date_partition_verification": {
                        "partition_mode": "half_open_end_date",
                        "partition_union_matches_baseline": True,
                        "partition_missing_row_count": 0,
                    },
                    "judgment": "储值卡明细已完成 HTTP 回证，当前可按默认空 Search 单请求进入 capture；Search 已确认只对卡号类值稳定收敛，时间窗口已验证为半开区间。",
                },
                "conclusion": {
                    "next_focus": "储值卡明细已满足 capture admit 条件，下一步按默认空 Search 单请求准入 capture，并把 Search 语义限制收进文档。"
                },
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "stored-value-capture-research-20260323-000121.json",
        json.dumps({"capture_batch_id": "stored-value-batch-001"}, ensure_ascii=False),
    )
    _write(
        analysis_root / "stored-value-capture-admission-20260323-000122.json",
        json.dumps({"capture_batch_id": "stored-value-admit-001"}, ensure_ascii=False),
    )

    board = build_api_maturity_board(repo_root, analysis_root)
    routes = {entry["route"]: entry for entry in board["entries"]}

    assert routes["储值卡明细 / GetDIYReportData"]["stage"] == "已HTTP回证"
    assert routes["储值卡明细 / GetDIYReportData"]["capture_written_once"] is True
    assert routes["储值卡明细 / GetDIYReportData"]["latest_capture_batch_id"] == "stored-value-admit-001"
    assert routes["储值卡明细 / GetDIYReportData"]["latest_capture_mode"] == "admission"
    assert routes["储值卡明细 / GetDIYReportData"]["capture_parameter_plan"]["default_Search"] == ""
    assert routes["储值卡明细 / GetDIYReportData"]["capture_parameter_plan"]["page_mode"] == "single_request_half_open_date_verified"
    assert routes["储值卡明细 / GetDIYReportData"]["blocking_issues"] == []


def test_build_api_maturity_board_tracks_product_sales_snapshot_evidence_and_runtime(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"

    empty_ledger = _ledger([])
    _write(
        repo_root / "docs" / "erp" / "sales-ledger.md",
        _ledger(
            [
                (
                    "商品销售情况",
                    "YisEposReport/SelSaleReportData",
                    "已确认是稳定的商品维度聚合结果快照",
                    "结果快照",
                    "单请求快照",
                )
            ]
        ),
    )
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "member-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "payment-and-doc-ledger.md", empty_ledger)

    page_research = {
        "pages": [
            {
                "title": "商品销售情况",
                "status": "ok",
                "menu_target_title": "商品销售情况",
                "menu_root_name": "报表管理",
                "group_name": "综合分析",
                "menu_path": ["报表管理", "综合分析", "商品销售情况"],
                "target_menu_path": ["报表管理", "综合分析", "商品销售情况"],
                "grain_route": "single_route",
                "endpoint_summaries": [{"endpoint": "SelSaleReportData", "is_data_endpoint": True, "max_row_count": 1356}],
                "source_candidates": ["SelSaleReportData"],
                "result_snapshot_candidates": [],
                "recommended_capture_strategy": "baseline_single_request",
                "payload_hints": {"pagination_fields": [], "enum_fields": []},
                "single_variable_probe_results": [],
            }
        ]
    }
    _write(analysis_root / "yeusoft-page-research-20260325-000100.json", json.dumps(page_research, ensure_ascii=False))
    menu_coverage = {
        "summary": {
            "audit_complete": True,
            "all_visible_pages_classified": True,
            "menu_node_count": 3,
            "container_only_count": 0,
            "clickable_page_count": 1,
            "covered_count": 1,
            "visible_but_untracked_count": 0,
            "visible_but_failed_count": 0,
            "unknown_pages": [],
            "unmatched_registry_targets": [],
        },
        "pages": [
            {
                "title": "商品销售情况",
                "page_title": "商品销售情况",
                "menu_path": ["报表管理", "综合分析", "商品销售情况"],
                "root_name": "报表管理",
                "group_name": "综合分析",
                "coverage_status": "covered",
                "coverage_confidence": "high",
                "matched_registry_titles": ["商品销售情况"],
            }
        ],
        "containers": [],
    }
    _write(analysis_root / "menu-coverage-audit-20260325-000110.json", json.dumps(menu_coverage, ensure_ascii=False))
    _write(
        analysis_root / "product-sales-snapshot-evidence-chain-20260325-000120.json",
        json.dumps(
            {
                "product_sales_snapshot": {
                    "capture_admission_ready": True,
                    "blocking_issues": [],
                    "capture_parameter_plan": {
                        "default_bdate": "20250301",
                        "default_edate": "20260401",
                        "default_warecause": "",
                        "default_spenum": "",
                        "page_mode": "single_request_declared_total_match",
                    },
                    "capture_page_summary": {
                        "declared_total_count": 1356,
                        "observed_total_rows": 1356,
                        "capture_complete": True,
                    },
                    "judgment": "商品销售情况已完成 HTTP 回证，默认时间窗单请求返回行数已匹配服务端声明总数，可进入 snapshot capture。",
                },
                "conclusion": {
                    "next_focus": "商品销售情况已满足 snapshot capture 条件；下一步按默认时间窗单请求写入 capture。"
                },
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "product-sales-snapshot-capture-admission-20260325-000121.json",
        json.dumps({"capture_batch_id": "product-sales-snapshot-batch-001"}, ensure_ascii=False),
    )

    board = build_api_maturity_board(repo_root, analysis_root)
    routes = {entry["route"]: entry for entry in board["entries"]}

    entry = routes["商品销售情况 / SelSaleReportData"]
    assert entry["stage"] == "已HTTP回证"
    assert entry["source_kind"] == "结果快照"
    assert entry["capture_admission_ready"] is True
    assert entry["capture_written_once"] is True
    assert entry["latest_capture_batch_id"] == "product-sales-snapshot-batch-001"
    assert entry["latest_capture_mode"] == "admission"
    assert entry["mainline_ready"] is False


def test_build_api_maturity_board_tracks_daily_payment_snapshot_evidence_and_runtime(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"

    empty_ledger = _ledger([])
    _write(repo_root / "docs" / "erp" / "sales-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "member-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", empty_ledger)
    _write(
        repo_root / "docs" / "erp" / "payment-and-doc-ledger.md",
        _ledger(
            [
                (
                    "每日流水单",
                    "JyApi/ReconciliationAnalysis/SelectRetailDocPaymentSlip",
                    "支付流水结果接口，高价值但需继续摸清查询语义",
                    "需要扫枚举",
                    "结果快照",
                )
            ]
        ),
    )

    page_research = {
        "pages": [
            {
                "title": "每日流水单",
                "status": "ok",
                "menu_target_title": "每日流水单",
                "menu_root_name": "报表管理",
                "group_name": "对账报表",
                "menu_path": ["报表管理", "对账报表", "每日流水单"],
                "target_menu_path": ["报表管理", "对账报表", "每日流水单"],
                "grain_route": "single_route",
                "endpoint_summaries": [{"endpoint": "SelectRetailDocPaymentSlip", "is_data_endpoint": True, "max_row_count": 4045}],
                "source_candidates": ["SelectRetailDocPaymentSlip"],
                "result_snapshot_candidates": ["SelectRetailDocPaymentSlip"],
                "recommended_capture_strategy": "baseline_single_request",
                "payload_hints": {"pagination_fields": [], "enum_fields": ["SearchType"]},
                "single_variable_probe_results": [],
            }
        ]
    }
    _write(analysis_root / "yeusoft-page-research-20260325-000200.json", json.dumps(page_research, ensure_ascii=False))
    menu_coverage = {
        "summary": {
            "audit_complete": True,
            "all_visible_pages_classified": True,
            "menu_node_count": 3,
            "container_only_count": 0,
            "clickable_page_count": 1,
            "covered_count": 1,
            "visible_but_untracked_count": 0,
            "visible_but_failed_count": 0,
            "unknown_pages": [],
            "unmatched_registry_targets": [],
        },
        "pages": [
            {
                "title": "每日流水单",
                "page_title": "每日流水单",
                "menu_path": ["报表管理", "对账报表", "每日流水单"],
                "root_name": "报表管理",
                "group_name": "对账报表",
                "coverage_status": "covered",
                "coverage_confidence": "high",
                "matched_registry_titles": ["每日流水单"],
            }
        ],
        "containers": [],
    }
    _write(analysis_root / "menu-coverage-audit-20260325-000210.json", json.dumps(menu_coverage, ensure_ascii=False))
    _write(
        analysis_root / "daily-payment-snapshot-evidence-chain-20260325-000220.json",
        json.dumps(
            {
                "daily_payment_snapshot": {
                    "capture_admission_ready": True,
                    "blocking_issues": [],
                    "capture_parameter_plan": {
                        "default_menu_id": "E004006001",
                        "default_search_type": "1",
                        "page_mode": "single_request_no_pagination_fields",
                        "observed_total_rows": 4045,
                        "searchtype_semantics": {
                            "tested_values": ["", "1", "2", "3", "4", "5"],
                            "same_dataset_values": ["", "1", "2", "3", "4", "5"],
                            "different_dataset_values": [],
                            "error_values": [],
                            "same_dataset_for_tested_values": True,
                        },
                    },
                    "capture_page_summary": {
                        "observed_total_rows": 4045,
                        "capture_complete": True,
                    },
                    "judgment": "每日流水单已完成 HTTP 回证；默认窗口单请求返回稳定快照，且 SearchType 已验证为同一数据集，可进入 snapshot capture。",
                },
                "conclusion": {
                    "next_focus": "每日流水单已满足 snapshot capture 条件；下一步按默认窗口单请求写入 capture。"
                },
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "daily-payment-snapshot-capture-admission-20260325-000221.json",
        json.dumps({"capture_batch_id": "daily-payment-snapshot-batch-001"}, ensure_ascii=False),
    )

    board = build_api_maturity_board(repo_root, analysis_root)
    routes = {entry["route"]: entry for entry in board["entries"]}

    entry = routes["每日流水单 / SelectRetailDocPaymentSlip"]
    assert entry["stage"] == "已HTTP回证"
    assert entry["source_kind"] == "结果快照"
    assert entry["capture_admission_ready"] is True
    assert entry["capture_written_once"] is True
    assert entry["latest_capture_batch_id"] == "daily-payment-snapshot-batch-001"
    assert entry["latest_capture_mode"] == "admission"
    assert entry["mainline_ready"] is False


def test_build_api_maturity_board_tracks_member_sales_rank_snapshot_evidence_and_runtime(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"

    empty_ledger = _ledger([])
    _write(repo_root / "docs" / "erp" / "sales-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(
        repo_root / "docs" / "erp" / "member-ledger.md",
        _ledger(
            [
                ("会员消费排行", "YisEposReport/SelVipSaleRank", "会员消费排行结果快照", "结果快照", "结果快照"),
            ]
        ),
    )
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "payment-and-doc-ledger.md", empty_ledger)

    page_research = {
        "pages": [
            {
                "title": "会员消费排行榜",
                "status": "ok",
                "menu_target_title": "会员消费排行榜",
                "menu_root_name": "报表管理",
                "group_name": "会员报表",
                "menu_path": ["报表管理", "会员报表", "会员消费排行榜"],
                "target_menu_path": ["报表管理", "会员报表", "会员消费排行榜"],
                "grain_route": "single_route",
                "endpoint_summaries": [{"endpoint": "SelVipSaleRank", "is_data_endpoint": True, "max_row_count": 1204}],
                "source_candidates": [],
                "result_snapshot_candidates": ["SelVipSaleRank"],
                "recommended_capture_strategy": "baseline_single_request",
                "payload_hints": {"pagination_fields": ["page", "pagesize"], "enum_fields": []},
                "single_variable_probe_results": [],
            }
        ]
    }
    _write(analysis_root / "yeusoft-page-research-20260325-000200.json", json.dumps(page_research, ensure_ascii=False))
    menu_coverage = {
        "summary": {
            "audit_complete": True,
            "all_visible_pages_classified": True,
            "menu_node_count": 3,
            "container_only_count": 0,
            "clickable_page_count": 1,
            "covered_count": 1,
            "visible_but_untracked_count": 0,
            "visible_but_failed_count": 0,
            "unknown_pages": [],
            "unmatched_registry_targets": [],
        },
        "pages": [
            {
                "title": "会员消费排行榜",
                "page_title": "会员消费排行榜",
                "menu_path": ["报表管理", "会员报表", "会员消费排行榜"],
                "root_name": "报表管理",
                "group_name": "会员报表",
                "coverage_status": "covered",
                "coverage_confidence": "high",
                "matched_registry_titles": ["会员消费排行"],
            }
        ],
        "containers": [],
    }
    _write(analysis_root / "menu-coverage-audit-20260325-000210.json", json.dumps(menu_coverage, ensure_ascii=False))
    _write(
        analysis_root / "member-sales-rank-snapshot-evidence-chain-20260325-000220.json",
        json.dumps(
            {
                "member_sales_rank_snapshot": {
                    "capture_admission_ready": True,
                    "blocking_issues": [],
                    "capture_parameter_plan": {
                        "default_bdate": "20250301",
                        "default_edate": "20260401",
                        "default_page": 0,
                        "default_pagesize": 0,
                        "page_mode": "page_zero_full_fetch",
                        "declared_total_count": 1204,
                        "observed_total_rows": 1204,
                    },
                    "capture_page_summary": {
                        "request_payload": {"bdate": "20250301", "edate": "20260401", "page": 0, "pagesize": 0},
                        "declared_total_count": 1204,
                        "observed_total_rows": 1204,
                        "capture_complete": True,
                    },
                    "judgment": "会员消费排行已完成 HTTP 回证；page=0 当前稳定触发全量模式，且默认请求返回行数已匹配 Count，可进入 snapshot capture。",
                }
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "member-sales-rank-snapshot-capture-admission-20260325-000221.json",
        json.dumps({"capture_batch_id": "member-sales-rank-snapshot-batch-001"}, ensure_ascii=False),
    )

    board = build_api_maturity_board(repo_root, analysis_root)
    routes = {entry["route"]: entry for entry in board["entries"]}

    entry = routes["会员消费排行 / SelVipSaleRank"]
    assert entry["stage"] == "已HTTP回证"
    assert entry["source_kind"] == "结果快照"
    assert entry["capture_admission_ready"] is True
    assert entry["capture_written_once"] is True
    assert entry["latest_capture_batch_id"] == "member-sales-rank-snapshot-batch-001"
    assert entry["latest_capture_mode"] == "admission"
    assert entry["mainline_ready"] is False


def test_build_api_maturity_board_tracks_member_analysis_snapshot_evidence_and_runtime(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"

    empty_ledger = _ledger([])
    _write(repo_root / "docs" / "erp" / "sales-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(
        repo_root / "docs" / "erp" / "member-ledger.md",
        _ledger(
            [
                ("会员总和分析", "YisEposReport/SelVipAnalysisReport", "会员分析结果快照", "结果快照", "结果快照"),
            ]
        ),
    )
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "payment-and-doc-ledger.md", empty_ledger)

    page_research = {
        "pages": [
            {
                "title": "会员总和分析",
                "status": "ok",
                "menu_target_title": "会员总和分析",
                "menu_root_name": "报表管理",
                "group_name": "会员报表",
                "menu_path": ["报表管理", "会员报表", "会员总和分析"],
                "target_menu_path": ["报表管理", "会员报表", "会员总和分析"],
                "grain_route": "single_route",
                "endpoint_summaries": [{"endpoint": "SelVipAnalysisReport", "is_data_endpoint": True, "max_row_count": 25}],
                "source_candidates": [],
                "result_snapshot_candidates": ["SelVipAnalysisReport"],
                "recommended_capture_strategy": "baseline_single_request",
                "payload_hints": {"pagination_fields": ["page", "pagesize"], "enum_fields": ["tag", "type"]},
                "single_variable_probe_results": [],
            }
        ]
    }
    _write(analysis_root / "yeusoft-page-research-20260325-000300.json", json.dumps(page_research, ensure_ascii=False))
    menu_coverage = {
        "summary": {
            "audit_complete": True,
            "all_visible_pages_classified": True,
            "menu_node_count": 3,
            "container_only_count": 0,
            "clickable_page_count": 1,
            "covered_count": 1,
            "visible_but_untracked_count": 0,
            "visible_but_failed_count": 0,
            "unknown_pages": [],
            "unmatched_registry_targets": [],
        },
        "pages": [
            {
                "title": "会员总和分析",
                "page_title": "会员总和分析",
                "menu_path": ["报表管理", "会员报表", "会员总和分析"],
                "root_name": "报表管理",
                "group_name": "会员报表",
                "coverage_status": "covered",
                "coverage_confidence": "high",
                "matched_registry_titles": ["会员总和分析"],
            }
        ],
        "containers": [],
    }
    _write(analysis_root / "menu-coverage-audit-20260325-000310.json", json.dumps(menu_coverage, ensure_ascii=False))
    _write(
        analysis_root / "member-analysis-snapshot-evidence-chain-20260325-000320.json",
        json.dumps(
            {
                "member_analysis_snapshot": {
                    "capture_admission_ready": True,
                    "blocking_issues": [],
                    "capture_parameter_plan": {
                        "default_salebdate": "20250301",
                        "default_saleedate": "20250401",
                        "default_tag": "",
                        "default_type": "",
                        "default_page": 0,
                        "default_pagesize": 0,
                        "page_mode": "page_zero_full_fetch",
                        "observed_total_rows": 25,
                        "type_semantics": {
                            "tested_values": ["blank", "1", "2", "3"],
                            "same_dataset_values": ["1", "2", "3", "blank"],
                            "different_dataset_values": [],
                            "error_values": [],
                            "same_dataset_for_tested_values": True,
                        },
                        "tag_semantics": {
                            "tested_values": ["blank", "1", "2", "3"],
                            "same_dataset_values": ["blank"],
                            "different_dataset_values": ["1", "2", "3"],
                            "error_values": [],
                            "same_dataset_for_tested_values": False,
                        },
                    },
                    "capture_page_summary": {
                        "request_payload": {"salebdate": "20250301", "saleedate": "20250401", "page": 0, "pagesize": 0, "tag": "", "type": ""},
                        "observed_total_rows": 25,
                        "capture_complete": True,
                    },
                    "judgment": "会员总和分析已完成 HTTP 回证；page=0 当前稳定触发全量模式，type 对已测值仍是同一数据集，tag 会切结果子集，可进入 snapshot capture。",
                }
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "member-analysis-snapshot-capture-admission-20260325-000321.json",
        json.dumps({"capture_batch_id": "member-analysis-snapshot-batch-001"}, ensure_ascii=False),
    )

    board = build_api_maturity_board(repo_root, analysis_root)
    routes = {entry["route"]: entry for entry in board["entries"]}

    entry = routes["会员总和分析 / SelVipAnalysisReport"]
    assert entry["stage"] == "已HTTP回证"
    assert entry["source_kind"] == "结果快照"
    assert entry["capture_admission_ready"] is True
    assert entry["capture_written_once"] is True
    assert entry["latest_capture_batch_id"] == "member-analysis-snapshot-batch-001"
    assert entry["latest_capture_mode"] == "admission"
    assert entry["mainline_ready"] is False


def test_build_api_maturity_board_tracks_stored_value_summary_snapshot_evidence_and_runtime(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"

    empty_ledger = _ledger([])
    _write(repo_root / "docs" / "erp" / "sales-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "member-ledger.md", empty_ledger)
    _write(
        repo_root / "docs" / "erp" / "stored-value-ledger.md",
        _ledger(
            [
                ("储值按店汇总", "FXDIYReport/GetDIYReportData", "门店级汇总接口", "只能当结果快照", "结果快照"),
                ("储值卡汇总", "FXDIYReport/GetDIYReportData", "卡级汇总接口", "只能当结果快照", "结果快照"),
            ]
        ),
    )
    _write(repo_root / "docs" / "erp" / "payment-and-doc-ledger.md", empty_ledger)

    page_research = {
        "pages": [
            {
                "title": "储值按店汇总",
                "status": "ok",
                "menu_target_title": "储值按店汇总",
                "menu_root_name": "报表管理",
                "group_name": "会员报表",
                "menu_path": ["报表管理", "会员报表", "储值按店汇总"],
                "target_menu_path": ["报表管理", "会员报表", "储值按店汇总"],
                "grain_route": "single_route",
                "endpoint_summaries": [{"endpoint": "GetDIYReportData", "is_data_endpoint": True, "max_row_count": 1}],
                "source_candidates": [],
                "result_snapshot_candidates": ["GetDIYReportData"],
                "recommended_capture_strategy": "baseline_single_request",
                "payload_hints": {"pagination_fields": ["page", "pagesize"], "enum_fields": []},
                "single_variable_probe_results": [],
            },
            {
                "title": "储值卡汇总",
                "status": "ok",
                "menu_target_title": "储值卡汇总",
                "menu_root_name": "报表管理",
                "group_name": "会员报表",
                "menu_path": ["报表管理", "会员报表", "储值卡汇总"],
                "target_menu_path": ["报表管理", "会员报表", "储值卡汇总"],
                "grain_route": "single_route",
                "endpoint_summaries": [{"endpoint": "GetDIYReportData", "is_data_endpoint": True, "max_row_count": 19}],
                "source_candidates": [],
                "result_snapshot_candidates": ["GetDIYReportData"],
                "recommended_capture_strategy": "baseline_single_request",
                "payload_hints": {"pagination_fields": ["page", "pagesize"], "enum_fields": []},
                "single_variable_probe_results": [],
            },
        ]
    }
    _write(analysis_root / "yeusoft-page-research-20260325-000400.json", json.dumps(page_research, ensure_ascii=False))
    menu_coverage = {
        "summary": {
            "audit_complete": True,
            "all_visible_pages_classified": True,
            "menu_node_count": 4,
            "container_only_count": 0,
            "clickable_page_count": 2,
            "covered_count": 2,
            "visible_but_untracked_count": 0,
            "visible_but_failed_count": 0,
            "unknown_pages": [],
            "unmatched_registry_targets": [],
        },
        "pages": [
            {
                "title": "储值按店汇总",
                "page_title": "储值按店汇总",
                "menu_path": ["报表管理", "会员报表", "储值按店汇总"],
                "root_name": "报表管理",
                "group_name": "会员报表",
                "coverage_status": "covered",
                "coverage_confidence": "high",
                "matched_registry_titles": ["储值按店汇总"],
            },
            {
                "title": "储值卡汇总",
                "page_title": "储值卡汇总",
                "menu_path": ["报表管理", "会员报表", "储值卡汇总"],
                "root_name": "报表管理",
                "group_name": "会员报表",
                "coverage_status": "covered",
                "coverage_confidence": "high",
                "matched_registry_titles": ["储值卡汇总"],
            },
        ],
        "containers": [],
    }
    _write(analysis_root / "menu-coverage-audit-20260325-000410.json", json.dumps(menu_coverage, ensure_ascii=False))
    _write(
        analysis_root / "stored-value-card-summary-snapshot-evidence-chain-20260325-000420.json",
        json.dumps(
            {
                "stored_value_card_summary_snapshot": {
                    "capture_admission_ready": True,
                    "blocking_issues": [],
                    "capture_parameter_plan": {
                        "default_menuid": "E004004004",
                        "default_gridid": "E004004004_main",
                        "default_begin_date": "2025-03-01",
                        "default_end_date": "2026-04-01",
                        "default_search": "",
                        "page_mode": "single_request_page_field_ignored",
                        "observed_total_rows": 19,
                        "search_semantics": {
                            "tested_values": ["__no_match__", "vip_card:V001"],
                            "same_dataset_values": [],
                            "different_dataset_values": ["__no_match__", "vip_card:V001"],
                            "error_values": [],
                        },
                    },
                    "capture_page_summary": {
                        "observed_total_rows": 19,
                        "capture_complete": True,
                    },
                    "judgment": "储值卡汇总已完成 HTTP 回证；默认请求可稳定返回快照，Search 已验证可以切结果子集，可进入 snapshot capture。",
                }
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "stored-value-card-summary-snapshot-capture-admission-20260325-000421.json",
        json.dumps({"capture_batch_id": "stored-value-card-summary-batch-001"}, ensure_ascii=False),
    )
    _write(
        analysis_root / "stored-value-by-store-snapshot-evidence-chain-20260325-000430.json",
        json.dumps(
            {
                "stored_value_by_store_snapshot": {
                    "capture_admission_ready": True,
                    "blocking_issues": [],
                    "capture_parameter_plan": {
                        "default_menuid": "E004004003",
                        "default_gridid": "E004004003_main",
                        "default_begin_date": "2025-03-01",
                        "default_end_date": "2026-04-01",
                        "page_mode": "single_request_page_field_ignored",
                        "observed_total_rows": 1,
                    },
                    "capture_page_summary": {
                        "observed_total_rows": 1,
                        "capture_complete": True,
                    },
                    "judgment": "储值按店汇总已完成 HTTP 回证；默认请求可稳定返回门店级快照，可进入 snapshot capture。",
                }
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "stored-value-by-store-snapshot-capture-admission-20260325-000431.json",
        json.dumps({"capture_batch_id": "stored-value-by-store-batch-001"}, ensure_ascii=False),
    )

    board = build_api_maturity_board(repo_root, analysis_root)
    routes = {entry["route"]: entry for entry in board["entries"]}

    card_entry = routes["储值卡汇总 / GetDIYReportData"]
    assert card_entry["stage"] == "已HTTP回证"
    assert card_entry["source_kind"] == "结果快照"
    assert card_entry["capture_admission_ready"] is True
    assert card_entry["capture_written_once"] is True
    assert card_entry["latest_capture_batch_id"] == "stored-value-card-summary-batch-001"
    assert card_entry["latest_capture_mode"] == "admission"
    assert card_entry["mainline_ready"] is False

    by_store_entry = routes["储值按店汇总 / GetDIYReportData"]
    assert by_store_entry["stage"] == "已HTTP回证"
    assert by_store_entry["source_kind"] == "结果快照"
    assert by_store_entry["capture_admission_ready"] is True
    assert by_store_entry["capture_written_once"] is True
    assert by_store_entry["latest_capture_batch_id"] == "stored-value-by-store-batch-001"
    assert by_store_entry["latest_capture_mode"] == "admission"
    assert by_store_entry["mainline_ready"] is False


def test_build_api_maturity_board_applies_customer_evidence(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"

    empty_ledger = _ledger([])
    _write(
        repo_root / "docs" / "erp" / "sales-ledger.md",
        _ledger(
            [
                (
                    "客户资料",
                    "YisEposDeptClientSet/SelDeptList",
                    "当前更像客户主数据页，已确认主接口为 SelDeptList；当前账号 baseline 为空数据集",
                    "需要翻页",
                    "自动翻页",
                )
            ]
        ),
    )
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "member-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "payment-and-doc-ledger.md", empty_ledger)

    page_research = {
        "pages": [
            {
                "title": "客户资料",
                "status": "ok",
                "menu_target_title": "客户资料",
                "menu_root_name": "基础资料",
                "group_name": "",
                "menu_path": ["基础资料", "客户资料"],
                "target_menu_path": ["基础资料", "客户资料"],
                "grain_route": "single_route",
                "endpoint_summaries": [{"endpoint": "SelDeptList", "is_data_endpoint": True, "max_row_count": 0}],
                "source_candidates": ["SelDeptList"],
                "result_snapshot_candidates": [],
                "recommended_capture_strategy": "http_followup_with_pagination",
                "payload_hints": {"pagination_fields": ["page", "pagesize"], "enum_fields": []},
                "single_variable_probe_results": [],
            },
        ]
    }
    _write(analysis_root / "yeusoft-page-research-20260322-000100.json", json.dumps(page_research, ensure_ascii=False))
    menu_coverage = {
        "summary": {
            "audit_complete": True,
            "all_visible_pages_classified": True,
            "menu_node_count": 2,
            "container_only_count": 0,
            "clickable_page_count": 1,
            "covered_count": 1,
            "visible_but_untracked_count": 0,
            "visible_but_failed_count": 0,
            "unknown_pages": [],
            "unmatched_registry_targets": [],
        },
        "pages": [
            {
                "title": "客户资料",
                "page_title": "客户资料",
                "menu_path": ["基础资料", "客户资料"],
                "root_name": "基础资料",
                "group_name": "",
                "coverage_status": "covered",
                "coverage_confidence": "medium",
                "matched_registry_titles": [],
            }
        ],
        "containers": [],
    }
    _write(analysis_root / "menu-coverage-audit-20260322-000300.json", json.dumps(menu_coverage, ensure_ascii=False))
    _write(
        analysis_root / "customer-evidence-chain-20260322-000400.json",
        json.dumps(
            {
                "customer_list": {
                    "endpoint": "SelDeptList",
                    "judgment": "客户资料真实主接口已完成 HTTP 回证；当前账号下默认查询与 seed 参数均返回同一空集，可先按稳定空集主数据留痕。",
                    "capture_admission_ready": True,
                    "capture_parameter_plan": {
                        "default_deptname": "",
                        "baseline_page": 1,
                        "baseline_pagesize": 20,
                        "page_mode": "single_request_stable_empty_verified",
                        "empty_dataset_confirmed": True,
                    },
                    "parameter_semantics": {
                        "page": {"semantics": "same_dataset"},
                        "pagesize": {"semantics": "same_dataset"},
                        "deptname": {"semantics": "same_dataset"},
                    },
                    "blocking_issues": [],
                },
                "conclusion": {
                    "next_focus": "当前账号下客户资料已验证为稳定空集；可先按空集主数据 admit 进入 capture，并继续观察后续账号/页面上下文是否引入非空集合。"
                },
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "customer-capture-admission-20260322-000500.json",
        json.dumps(
            {
                "capture_batch_id": "customer-batch-001",
                "source_endpoint": "yeusoft.master.customer_list",
            },
            ensure_ascii=False,
        ),
    )

    board = build_api_maturity_board(repo_root, analysis_root)
    routes = {entry["route"]: entry for entry in board["entries"]}

    assert routes["客户资料 / SelDeptList"]["stage"] == "已HTTP回证"
    assert routes["客户资料 / SelDeptList"]["reliability_status"] == "中等可信"
    assert routes["客户资料 / SelDeptList"]["capture_admission_ready"] is True
    assert routes["客户资料 / SelDeptList"]["mainline_ready"] is True
    assert routes["客户资料 / SelDeptList"]["parameter_semantics"]["deptname"]["semantics"] == "same_dataset"
    assert routes["客户资料 / SelDeptList"]["blocking_issues"] == []
    assert routes["客户资料 / SelDeptList"]["capture_written_once"] is True
    assert routes["客户资料 / SelDeptList"]["latest_capture_batch_id"] == "customer-batch-001"
    assert routes["客户资料 / SelDeptList"]["latest_capture_mode"] == "admission"


def test_build_api_maturity_board_applies_member_maintenance_http_evidence(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"
    analysis_root.mkdir(parents=True)

    empty_ledger = _ledger([])
    _write(repo_root / "docs" / "erp" / "sales-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(
        repo_root / "docs" / "erp" / "member-ledger.md",
        _ledger(
            [
                (
                    "会员维护",
                    "YisEposVipReturnVisit/SelVipReturnVisitList",
                    "当前真实主接口已识别并完成 HTTP 回证，但 baseline 为空且 seed 参数仍未改变数据集",
                    "当前账号可能无数据；疑似依赖隐藏上下文",
                    "单请求",
                )
            ]
        ),
    )
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "payment-and-doc-ledger.md", empty_ledger)

    _write(
        analysis_root / "yeusoft-page-research-20260323-000100.json",
        json.dumps(
            {
                "pages": [
                    {
                        "title": "会员维护",
                        "status": "ok",
                        "menu_target_title": "会员维护",
                        "menu_root_name": "会员资料",
                        "group_name": "",
                        "menu_path": ["会员资料", "会员维护"],
                        "target_menu_path": ["会员资料", "会员维护"],
                        "grain_route": "enum_or_scope_route",
                        "endpoint_summaries": [
                            {"endpoint": "SelVipReturnVisitList", "is_data_endpoint": True, "max_row_count": 0}
                        ],
                        "source_candidates": ["SelVipReturnVisitList"],
                        "recommended_capture_strategy": "http_followup_with_pagination_and_enum",
                        "payload_hints": {
                            "pagination_fields": ["page", "pagesize"],
                            "date_fields": ["bdate", "edate", "brdate", "erdate"],
                            "search_fields": ["search"],
                            "enum_fields": ["type"],
                        },
                        "single_variable_probe_results": [],
                    }
                ]
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "menu-coverage-audit-20260323-000200.json",
        json.dumps(
            {
                "summary": {
                    "audit_complete": True,
                    "all_visible_pages_classified": True,
                    "menu_node_count": 3,
                    "container_only_count": 0,
                    "clickable_page_count": 1,
                    "covered_count": 1,
                    "visible_but_untracked_count": 0,
                    "visible_but_failed_count": 0,
                    "unknown_pages": [],
                    "unmatched_registry_targets": [],
                },
                "pages": [
                    {
                        "title": "会员维护",
                        "page_title": "会员维护",
                        "menu_path": ["会员资料", "会员维护"],
                        "root_name": "会员资料",
                        "group_name": "",
                        "coverage_status": "covered",
                        "coverage_confidence": "medium",
                        "matched_registry_titles": [],
                    }
                ],
                "containers": [],
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "member-maintenance-evidence-chain-20260323-000300.json",
        json.dumps(
            {
                "member_maintenance": {
                    "capture_parameter_plan": {
                        "baseline_page": 1,
                        "baseline_pagesize": 20,
                        "type_seed_values": ["消费回访", "其他回访"],
                        "page_mode": "single_request_stable_empty_verified",
                        "empty_dataset_confirmed": True,
                    },
                    "capture_admission_ready": True,
                    "parameter_semantics": {
                        "type": {"semantics": "same_dataset"},
                    },
                    "blocking_issues": [],
                    "judgment": "会员维护真实主接口已完成 HTTP 回证；当前账号下默认查询与 seed 参数均返回同一空集，可先按稳定空集主数据留痕。",
                },
                "conclusion": {
                    "next_focus": "当前账号下会员维护已验证为稳定空集；可先按空集主数据 admit 进入 capture，并继续观察后续账号/页面上下文是否引入非空集合。"
                },
            },
            ensure_ascii=False,
        ),
    )

    board = build_api_maturity_board(repo_root, analysis_root)
    routes = {entry["route"]: entry for entry in board["entries"]}

    entry = routes["会员维护 / SelVipReturnVisitList"]
    assert entry["stage"] == "已HTTP回证"
    assert entry["reliability_status"] == "中等可信"
    assert entry["capture_admission_ready"] is True
    assert entry["mainline_ready"] is True
    assert entry["parameter_semantics"]["type"]["semantics"] == "same_dataset"
    assert entry["blocking_issues"] == []
    assert entry["capture_parameter_plan"]["type_seed_values"] == ["消费回访", "其他回访"]


def test_build_api_maturity_board_marks_return_detail_sql_error_blocker(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"

    empty_ledger = _ledger([])
    _write(repo_root / "docs" / "erp" / "sales-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "member-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", empty_ledger)
    _write(
        repo_root / "docs" / "erp" / "payment-and-doc-ledger.md",
        _ledger(
            [
                (
                    "退货明细",
                    "YisEposReport/SelReturnStockList",
                    "当前真实数据接口已识别，但默认参数会触发服务端 SQL 截断错误，暂不能准入主链",
                    "服务端错误；需要扫枚举",
                    "待识别",
                )
            ]
        ),
    )

    page_research = {
        "pages": [
            {
                "title": "退货明细",
                "status": "ok",
                "menu_target_title": "退货明细",
                "menu_root_name": "报表管理",
                "group_name": "进出报表",
                "menu_path": ["报表管理", "进出报表", "退货明细"],
                "target_menu_path": ["报表管理", "进出报表", "退货明细"],
                "grain_route": "single_route",
                "endpoint_summaries": [
                    {"endpoint": "GetViewGridList", "is_data_endpoint": False, "max_row_count": 0},
                    {"endpoint": "ReturnStockBaseInfo", "is_data_endpoint": False, "max_row_count": 0},
                    {"endpoint": "SelReturnStockList", "is_data_endpoint": True, "max_row_count": 0},
                ],
                "source_candidates": ["SelReturnStockList"],
                "result_snapshot_candidates": ["GetViewGridList", "ReturnStockBaseInfo"],
                "recommended_capture_strategy": "http_followup_with_enum_probe",
                "payload_hints": {"enum_fields": ["type"], "diy_context_fields": ["menuid", "gridid"]},
                "single_variable_probe_results": [],
            }
        ]
    }
    _write(analysis_root / "yeusoft-page-research-20260322-000100.json", json.dumps(page_research, ensure_ascii=False))
    menu_coverage = {
        "summary": {
            "audit_complete": True,
            "all_visible_pages_classified": True,
            "menu_node_count": 3,
            "container_only_count": 0,
            "clickable_page_count": 1,
            "covered_count": 1,
            "visible_but_untracked_count": 0,
            "visible_but_failed_count": 0,
            "unknown_pages": [],
            "unmatched_registry_targets": [],
        },
        "pages": [
            {
                "title": "退货明细",
                "page_title": "退货明细",
                "menu_path": ["报表管理", "进出报表", "退货明细"],
                "root_name": "报表管理",
                "group_name": "进出报表",
                "coverage_status": "covered",
                "coverage_confidence": "medium",
                "matched_registry_titles": [],
            }
        ],
        "containers": [],
    }
    _write(analysis_root / "menu-coverage-audit-20260322-000300.json", json.dumps(menu_coverage, ensure_ascii=False))

    board = build_api_maturity_board(repo_root, analysis_root)
    routes = {entry["route"]: entry for entry in board["entries"]}

    entry = routes["退货明细 / SelReturnStockList"]
    assert entry["blocking_issues"] == [
        "当前默认参数会触发服务端 SQL 截断错误",
        "尚未完成 type 合法值集合确认",
        "尚未确认页面附加参数是否影响服务端查询",
    ]
    assert entry["next_action"] == "先补全 ReturnStockBaseInfo 派生维度与隐藏上下文，再判断是页面遗漏参数还是服务端 SQL 本身失效"


def test_build_api_maturity_board_applies_return_detail_http_evidence(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"

    empty_ledger = _ledger([])
    _write(repo_root / "docs" / "erp" / "sales-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "member-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", empty_ledger)
    _write(
        repo_root / "docs" / "erp" / "payment-and-doc-ledger.md",
        _ledger(
            [
                (
                    "退货明细",
                    "YisEposReport/SelReturnStockList",
                    "当前真实数据接口已识别，但默认参数会触发服务端 SQL 截断错误，暂不能准入主链",
                    "服务端错误；需要扫枚举",
                    "待识别",
                )
            ]
        ),
    )

    page_research = {
        "pages": [
            {
                "title": "退货明细",
                "status": "ok",
                "menu_target_title": "退货明细",
                "menu_root_name": "报表管理",
                "group_name": "进出报表",
                "menu_path": ["报表管理", "进出报表", "退货明细"],
                "target_menu_path": ["报表管理", "进出报表", "退货明细"],
                "grain_route": "enum_or_scope_route",
                "endpoint_summaries": [
                    {"endpoint": "ReturnStockBaseInfo", "is_data_endpoint": False, "max_row_count": 11},
                    {"endpoint": "SelReturnStockList", "is_data_endpoint": True, "max_row_count": 0},
                ],
                "source_candidates": [],
                "result_snapshot_candidates": ["ReturnStockBaseInfo"],
                "recommended_capture_strategy": "http_followup_with_enum_probe",
                "payload_hints": {"enum_fields": ["type"], "org_fields": ["warecause", "spenum"]},
                "single_variable_probe_results": [],
            }
        ]
    }
    _write(analysis_root / "yeusoft-page-research-20260322-000100.json", json.dumps(page_research, ensure_ascii=False))
    menu_coverage = {
        "summary": {
            "audit_complete": True,
            "all_visible_pages_classified": True,
            "menu_node_count": 3,
            "container_only_count": 0,
            "clickable_page_count": 1,
            "covered_count": 1,
            "visible_but_untracked_count": 0,
            "visible_but_failed_count": 0,
            "unknown_pages": [],
            "unmatched_registry_targets": [],
        },
        "pages": [
            {
                "title": "退货明细",
                "page_title": "退货明细",
                "menu_path": ["报表管理", "进出报表", "退货明细"],
                "root_name": "报表管理",
                "group_name": "进出报表",
                "coverage_status": "covered",
                "coverage_confidence": "medium",
                "matched_registry_titles": [],
            }
        ],
        "containers": [],
    }
    _write(analysis_root / "menu-coverage-audit-20260322-000300.json", json.dumps(menu_coverage, ensure_ascii=False))
    _write(
        analysis_root / "return-detail-evidence-chain-20260322-000400.json",
        json.dumps(
                {
                    "return_detail": {
                        "capture_parameter_plan": {"type_seed_values": ["0", "1", "2", "3", "4", "5"]},
                        "type_probe_summary": {
                            "tested_values": ["blank", "0", "1", "2", "3", "4", "5"],
                            "successful_values": [],
                        },
                        "base_info_filter_coverage": {
                            "visible_titles": ["品牌", "订单来源"],
                            "mapped_titles": ["品牌", "订单来源"],
                        "unmapped_titles": [],
                        "mapping_complete": True,
                    },
                    "blocking_issues": [
                        "当前 seed type 值全部触发服务端错误",
                        "服务端 SQL 截断错误仍未解除",
                        "尚未确认可稳定返回数据的 type 取值",
                    ],
                    "judgment": "真实接口已通过 HTTP 回证，但当前 seed type 集仍全部触发服务端错误",
                },
                "conclusion": {
                    "next_focus": "优先通过页面动作或更窄过滤条件定位可成功返回数据的 type 值，再评估是否进入 capture 主链"
                },
            },
            ensure_ascii=False,
        ),
    )

    board = build_api_maturity_board(repo_root, analysis_root)
    routes = {entry["route"]: entry for entry in board["entries"]}

    entry = routes["退货明细 / SelReturnStockList"]
    assert entry["stage"] == "已HTTP回证"
    assert entry["capture_parameter_plan"] == {"type_seed_values": ["0", "1", "2", "3", "4", "5"]}
    assert entry["blocking_issues"] == [
        "当前 seed type 值全部触发服务端错误",
        "服务端 SQL 截断错误仍未解除",
        "尚未确认可稳定返回数据的 type 取值",
        "已补测祖先状态暴露的 type=4/5 候选值，仍全部触发服务端错误",
        "ReturnStockBaseInfo 当前 11 个可见筛选维度都已纳入 probe，问题已不在可见筛选遗漏",
    ]


def test_build_api_maturity_board_applies_return_detail_ui_probe_findings(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"

    empty_ledger = _ledger([])
    _write(repo_root / "docs" / "erp" / "sales-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "member-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", empty_ledger)
    _write(
        repo_root / "docs" / "erp" / "payment-and-doc-ledger.md",
        _ledger(
            [
                (
                    "退货明细",
                    "YisEposReport/SelReturnStockList",
                    "当前真实数据接口已识别，但默认参数会触发服务端 SQL 截断错误，暂不能准入主链",
                    "服务端错误；需要扫枚举",
                    "待识别",
                )
            ]
        ),
    )

    page_research = {
        "pages": [
            {
                "title": "退货明细",
                "status": "ok",
                "menu_target_title": "退货明细",
                "menu_root_name": "报表管理",
                "group_name": "进出报表",
                "menu_path": ["报表管理", "进出报表", "退货明细"],
                "target_menu_path": ["报表管理", "进出报表", "退货明细"],
                "grain_route": "enum_or_scope_route",
                "endpoint_summaries": [
                    {"endpoint": "ReturnStockBaseInfo", "is_data_endpoint": False, "max_row_count": 11},
                    {"endpoint": "SelReturnStockList", "is_data_endpoint": True, "max_row_count": 0},
                ],
                "source_candidates": [],
                "result_snapshot_candidates": ["ReturnStockBaseInfo"],
                "recommended_capture_strategy": "http_followup_with_enum_probe",
                "payload_hints": {"enum_fields": ["type"], "org_fields": ["warecause", "spenum"]},
                "single_variable_probe_results": [],
            }
        ]
    }
    _write(analysis_root / "yeusoft-page-research-20260322-000100.json", json.dumps(page_research, ensure_ascii=False))
    menu_coverage = {
        "summary": {
            "audit_complete": True,
            "all_visible_pages_classified": True,
            "menu_node_count": 3,
            "container_only_count": 0,
            "clickable_page_count": 1,
            "covered_count": 1,
            "visible_but_untracked_count": 0,
            "visible_but_failed_count": 0,
            "unknown_pages": [],
            "unmatched_registry_targets": [],
        },
        "pages": [
            {
                "title": "退货明细",
                "page_title": "退货明细",
                "menu_path": ["报表管理", "进出报表", "退货明细"],
                "root_name": "报表管理",
                "group_name": "进出报表",
                "coverage_status": "covered",
                "coverage_confidence": "medium",
                "matched_registry_titles": [],
            }
        ],
        "containers": [],
    }
    _write(analysis_root / "menu-coverage-audit-20260322-000300.json", json.dumps(menu_coverage, ensure_ascii=False))
    _write(
        analysis_root / "return-detail-evidence-chain-20260322-000400.json",
        json.dumps(
                {
                    "return_detail": {
                        "capture_parameter_plan": {"type_seed_values": ["0", "1", "2", "3", "4", "5"]},
                        "type_probe_summary": {
                            "tested_values": ["blank", "0", "1", "2", "3", "4", "5"],
                            "successful_values": [],
                        },
                        "base_info_filter_coverage": {
                            "visible_titles": ["品牌", "订单来源"],
                            "mapped_titles": ["品牌", "订单来源"],
                        "unmapped_titles": [],
                        "mapping_complete": True,
                    },
                    "blocking_issues": [
                        "当前 seed type 值全部触发服务端错误",
                        "服务端 SQL 截断错误仍未解除",
                        "尚未确认可稳定返回数据的 type 取值",
                    ],
                    "judgment": "真实接口已通过 HTTP 回证，但当前 seed type 集仍全部触发服务端错误",
                },
                "conclusion": {
                    "next_focus": "优先通过页面动作或更窄过滤条件定位可成功返回数据的 type 值，再评估是否进入 capture 主链"
                },
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "return-detail-ui-probe-20260324-220503.json",
        json.dumps(
            {
                "baseline": {
                    "return_detail_post_data": {"menuid": "E004003004", "gridid": "E004003004_1", "type": ""},
                    "component_ancestry_ref_states_after_query": [
                        {
                            "ref_name": "salesReturnDetail",
                            "component_name": "salesReturnDetail",
                            "props_data_keys": ["showLoading"],
                            "matched_keys": [],
                        },
                        {
                            "ref_name": "navmenu",
                            "component_name": None,
                            "props_data_keys": [],
                            "matched_keys": [],
                        },
                    ],
                    "component_diagnostics_after_query": [],
                    "method_owner_candidates_after_query": [{"name": "salesReturnDetailReport", "matched_methods": ["RTM_searchConditions"]}],
                    "component_ancestry_method_sources_after_query": [
                        {
                            "depth": 0,
                            "methods": [
                                {"name": "RTM_searchConditions", "preview": "function () { [native code] }"},
                                {"name": "RTM_getReportInfo", "preview": "function () { [native code] }"},
                                {"name": "getDataList", "preview": "function () { [native code] }"},
                            ],
                        },
                        {
                            "depth": 1,
                            "methods": [
                                {"name": "GetMenuList", "preview": "function () { [native code] }"},
                                {"name": "getPermission", "preview": "function () { [native code] }"},
                            ],
                        },
                    ],
                    "page_component_state_after_query": {
                        "safe_method_sources": {
                            "RTM_searchConditions": {"preview": "function () { [native code] }"},
                            "RTM_getReportInfo": {"preview": "function () { [native code] }"},
                        },
                        "refs_snapshot": {
                            "RTM_reportTable": {
                                "snapshot": {
                                    "searchConditions": {"type": "function"},
                                    "searchDataInfo": {"type": "function"},
                                    "pageCondition": {"type": "function"},
                                    "getReportInfo": {"type": "function"},
                                    "conditionStr": {"type": "function"},
                                },
                                "nested_snapshots": {"vxeTable": {"otherCondition": ""}},
                                "special_snapshot": {
                                    "vxeTable_snapshot": {"database_snapshot": {"DateBaseName": "FXDATABASE"}},
                                },
                            }
                        },
                    },
                    "table_ref_indexeddb_after_query": {
                        "target_database": {"object_store_names": []}
                    },
                    "component_store_state_after_query": {
                        "store_state_snapshot": {"cleardata": False},
                        "root_data_snapshot": {},
                    },
                    "component_global_storage_after_query": {
                        "local_storage_entries": [{"key": "yis_pc_logindata"}],
                        "session_storage_entries": [],
                        "vm_inject_snapshot": {"databaseTableName": ""},
                    },
                    "component_injection_context_after_query": {
                        "parent_fields_snapshot": {
                            "menuItemId": {"type": "object", "keys": ["salesReturnDetailReport"]},
                            "reportLists": {"type": "array", "length": 8},
                        },
                        "root_data_fields_snapshot": {},
                    },
                },
                "probes": [
                    {"label": "品牌", "return_detail_post_data": {"menuid": "E004003004", "gridid": "E004003004_1", "type": ""}},
                    {"label": "component_method:RTM_searchConditions", "component_method_step": {"key": "component_method_RTM_searchConditions", "request_delta": {"requests": []}}},
                    {"label": "component_method:RTM_getReportInfo", "component_method_step": {"key": "component_method_RTM_getReportInfo", "request_delta": {"requests": []}}},
                ],
                "ref_method_sources": [
                    {
                        "methods": {
                            "searchConditions": {"preview": "function () { [native code] }"},
                            "searchDataInfo": {"preview": "function () { [native code] }"},
                            "pageCondition": {"preview": "function () { [native code] }"},
                            "getReportInfo": {"preview": "function () { [native code] }"},
                            "conditionStr": {"preview": "function () { [native code] }"},
                        }
                    }
                ],
            },
            ensure_ascii=False,
        ),
    )

    board = build_api_maturity_board(repo_root, analysis_root)
    routes = {entry["route"]: entry for entry in board["entries"]}

    entry = routes["退货明细 / SelReturnStockList"]
    assert "页面真实点击后的查询请求仍未改变 post body" in entry["blocking_issues"]
    assert "组件诊断仍未暴露 route-level 过滤模型" in entry["blocking_issues"]
    assert "已定位 RTM_searchConditions/RTM_getReportInfo，但调用后仍未触发新请求" in entry["blocking_issues"]
    assert "RTM_reportTable 目前只暴露方法与 vxeTable 空条件状态，仍未看到可写筛选模型" in entry["blocking_issues"]
    assert "RTM_searchConditions/RTM_getReportInfo 当前只暴露 native code 包装，仍无法从函数体反推出隐藏上下文" in entry["blocking_issues"]
    assert "RTM_reportTable.vxeTable.database 已指向 FXDATABASE，但浏览器实际打开后 object_store_names 为空，salesReturnDetailReport 并未落成本地表" in entry["blocking_issues"]
    assert "RTM_reportTable.searchConditions/searchDataInfo/pageCondition/getReportInfo/conditionStr 当前都只暴露 native code 包装" in entry["blocking_issues"]
    assert "salesReturnDetailReport 根组件的查询/加载方法当前也只暴露 native code 包装，无法继续从根组件函数体反推上下文注入链" in entry["blocking_issues"]
    assert "salesReturnDetailReport 父链壳层方法当前也只暴露 native code 包装，说明更早的菜单/页面注入链同样不可从函数体继续回溯" in entry["blocking_issues"]
    assert "salesReturnDetail 自身 ref 当前只拿到 showLoading 回调，父链 navmenu 也未见任何附加数据载荷，说明壳层 ref 仍不是缺失退货数据的来源" in entry["blocking_issues"]
    assert "store/root 当前只见 cleardata=false 与空 root_data_snapshot，仍未见任何退货数据缓存" in entry["blocking_issues"]
    assert "localStorage/sessionStorage/window 当前只见登录态与通用字段，salesReturnDetailReport.vm 的 databaseTableName 仍为空" in entry["blocking_issues"]
    assert "route/parent 注入上下文当前只有 menuItemId/reportLists 等壳层信息，未见额外退货查询参数" in entry["blocking_issues"]
    assert "已补测祖先状态暴露的 type=4/5 候选值，仍全部触发服务端错误" in entry["blocking_issues"]
    assert "ReturnStockBaseInfo 当前 11 个可见筛选维度都已纳入 probe，问题已不在可见筛选遗漏" in entry["blocking_issues"]


def test_build_api_maturity_board_marks_return_detail_capture_research_runtime(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"

    empty_ledger = _ledger([])
    _write(repo_root / "docs" / "erp" / "sales-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "member-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", empty_ledger)
    _write(
        repo_root / "docs" / "erp" / "payment-and-doc-ledger.md",
        _ledger(
            [
                (
                    "退货明细",
                    "YisEposReport/SelReturnStockList",
                    "当前真实数据接口已识别，但默认参数会触发服务端 SQL 截断错误，暂不能准入主链",
                    "服务端错误；需要扫枚举",
                    "待识别",
                )
            ]
        ),
    )

    _write(
        analysis_root / "yeusoft-page-research-20260322-000100.json",
        json.dumps(
            {
                "pages": [
                    {
                        "title": "退货明细",
                        "status": "ok",
                        "menu_target_title": "退货明细",
                        "menu_root_name": "报表管理",
                        "group_name": "进出报表",
                        "menu_path": ["报表管理", "进出报表", "退货明细"],
                        "target_menu_path": ["报表管理", "进出报表", "退货明细"],
                        "grain_route": "enum_or_scope_route",
                        "endpoint_summaries": [
                            {"endpoint": "SelReturnStockList", "is_data_endpoint": True, "max_row_count": 0}
                        ],
                        "source_candidates": ["SelReturnStockList"],
                        "result_snapshot_candidates": [],
                        "recommended_capture_strategy": "http_followup_with_enum_probe",
                        "payload_hints": {"enum_fields": ["type"]},
                        "single_variable_probe_results": [],
                    }
                ]
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "menu-coverage-audit-20260322-000300.json",
        json.dumps(
            {
                "summary": {
                    "audit_complete": True,
                    "all_visible_pages_classified": True,
                    "menu_node_count": 3,
                    "container_only_count": 0,
                    "clickable_page_count": 1,
                    "covered_count": 1,
                    "visible_but_untracked_count": 0,
                    "visible_but_failed_count": 0,
                    "unknown_pages": [],
                    "unmatched_registry_targets": [],
                },
                "pages": [
                    {
                        "title": "退货明细",
                        "page_title": "退货明细",
                        "menu_path": ["报表管理", "进出报表", "退货明细"],
                        "root_name": "报表管理",
                        "group_name": "进出报表",
                        "coverage_status": "covered",
                        "coverage_confidence": "medium",
                        "matched_registry_titles": [],
                    }
                ],
                "containers": [],
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "return-detail-evidence-chain-20260322-000400.json",
        json.dumps(
            {
                "return_detail": {
                    "capture_parameter_plan": {"type_seed_values": ["0", "1", "2", "3"]},
                    "blocking_issues": [
                        "当前 seed type 值全部触发服务端错误",
                        "服务端 SQL 截断错误仍未解除",
                    ],
                }
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "return-detail-capture-research-20260324-000500.json",
        json.dumps(
            {
                "capture_batch_id": "return-detail-batch-001",
                "source_endpoint": "yeusoft.docs.return_detail",
            },
            ensure_ascii=False,
        ),
    )

    board = build_api_maturity_board(repo_root, analysis_root)
    entry = {item["route"]: item for item in board["entries"]}["退货明细 / SelReturnStockList"]

    assert entry["capture_written_once"] is True
    assert entry["latest_capture_batch_id"] == "return-detail-batch-001"
    assert entry["latest_capture_mode"] == "research"


def test_build_api_maturity_board_applies_receipt_confirmation_http_evidence(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"

    empty_ledger = _ledger([])
    _write(repo_root / "docs" / "erp" / "sales-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "member-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", empty_ledger)
    _write(
        repo_root / "docs" / "erp" / "payment-and-doc-ledger.md",
        _ledger(
            [
                (
                    "收货确认",
                    "JyApi/EposDoc/SelDocConfirmList",
                    "当前真实主接口已识别并完成 HTTP 回证，但 seed 参数仍未改变数据集，疑似依赖隐藏页面上下文或选中行动作链",
                    "需要补页面动作链；需要确认全量边界",
                    "待识别",
                )
            ]
        ),
    )

    page_research = {
        "pages": [
            {
                "title": "收货确认",
                "status": "ok",
                "menu_target_title": "收货确认",
                "menu_root_name": "单据管理",
                "group_name": "上级往来",
                "menu_path": ["单据管理", "上级往来", "收货确认"],
                "target_menu_path": ["单据管理", "上级往来", "收货确认"],
                "grain_route": "single_route",
                "endpoint_summaries": [
                    {"endpoint": "GetViewGridList", "is_data_endpoint": False, "max_row_count": 0},
                    {"endpoint": "SelDocConfirmList", "is_data_endpoint": True, "max_row_count": 2},
                ],
                "source_candidates": ["SelDocConfirmList"],
                "recommended_capture_strategy": "http_followup_with_action_chain",
                "payload_hints": {"pagination_fields": ["page", "pageSize"], "search_fields": ["time", "search"]},
                "single_variable_probe_results": [],
            }
        ]
    }
    _write(analysis_root / "yeusoft-page-research-20260322-000100.json", json.dumps(page_research, ensure_ascii=False))
    menu_coverage = {
        "summary": {
            "audit_complete": True,
            "all_visible_pages_classified": True,
            "menu_node_count": 3,
            "container_only_count": 0,
            "clickable_page_count": 1,
            "covered_count": 1,
            "visible_but_untracked_count": 0,
            "visible_but_failed_count": 0,
            "unknown_pages": [],
            "unmatched_registry_targets": [],
        },
        "pages": [
            {
                "title": "收货确认",
                "page_title": "收货确认",
                "menu_path": ["单据管理", "上级往来", "收货确认"],
                "root_name": "单据管理",
                "group_name": "上级往来",
                "coverage_status": "covered",
                "coverage_confidence": "medium",
                "matched_registry_titles": [],
            }
        ],
        "containers": [],
    }
    _write(analysis_root / "menu-coverage-audit-20260322-000300.json", json.dumps(menu_coverage, ensure_ascii=False))
    _write(
        analysis_root / "receipt-confirmation-evidence-chain-20260322-000400.json",
        json.dumps(
            {
                "receipt_confirmation": {
                    "capture_parameter_plan": {
                        "page_seed_values": ["page=1,pagesize=20", "page=2,pagesize=20"],
                        "page_mode": "single_request_same_dataset_verified",
                    },
                    "blocking_issues": [],
                    "secondary_route_blocking_issues": [
                        "单据确认动作链仍依赖页面选中行或隐藏动作链",
                        "物流信息动作链仍依赖页面选中行或隐藏动作链",
                        "扫描校验动作链仍待识别",
                    ],
                    "capture_admission_ready": True,
                    "judgment": "真实主接口已通过 HTTP 回证；当前 seed 参数 page/pageSize/time/search 均未改变数据集，说明主列表可先按空 payload 准入 capture，而单据确认 / 物流信息 / 扫描校验应拆成后续二级动作链。",
                },
                "conclusion": {
                    "next_focus": "收货确认主列表可先按空 payload 准入 capture；继续验证页面选中行和详情/确认动作链是否会补充隐藏参数或明细接口。"
                },
            },
            ensure_ascii=False,
        ),
    )

    board = build_api_maturity_board(repo_root, analysis_root)
    routes = {entry["route"]: entry for entry in board["entries"]}

    entry = routes["收货确认 / SelDocConfirmList"]
    assert entry["stage"] == "已HTTP回证"
    assert entry["blocking_issues"] == []
    assert entry["capture_parameter_plan"] == {
        "page_seed_values": ["page=1,pagesize=20", "page=2,pagesize=20"],
        "page_mode": "single_request_same_dataset_verified",
    }
    assert entry["capture_admission_ready"] is True
    assert entry["secondary_route_blocking_issues"] == [
        "单据确认动作链仍依赖页面选中行或隐藏动作链",
        "物流信息动作链仍依赖页面选中行或隐藏动作链",
        "扫描校验动作链仍待识别",
    ]
    assert entry["next_action"].startswith("收货确认主列表可先按空 payload")


def test_build_api_maturity_board_applies_store_stocktaking_http_evidence(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"
    analysis_root.mkdir(parents=True)

    empty_ledger = _ledger([])
    _write(repo_root / "docs" / "erp" / "sales-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "member-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", empty_ledger)
    _write(
        repo_root / "docs" / "erp" / "payment-and-doc-ledger.md",
        _ledger(
            [
                (
                    "门店盘点单",
                    "JyApi/EposDoc/SelDocManageList",
                    "当前真实主列表接口已识别并完成 HTTP 回证，stat 与日期范围都会改变数据范围，但查看明细/统计损溢/条码记录的二级动作链仍待识别",
                    "需要补动作链；需要确认正式保留值集",
                    "待识别",
                )
            ]
        ),
    )

    page_research = {
        "pages": [
            {
                "title": "门店盘点单",
                "status": "ok",
                "menu_target_title": "门店盘点单",
                "menu_root_name": "单据管理",
                "group_name": "盘点业务",
                "menu_path": ["单据管理", "盘点业务", "门店盘点单"],
                "target_menu_path": ["单据管理", "盘点业务", "门店盘点单"],
                "grain_route": "single_route",
                "endpoint_summaries": [
                    {"endpoint": "GetViewGridList", "is_data_endpoint": False, "max_row_count": 0},
                    {"endpoint": "SelDocManageList", "is_data_endpoint": True, "max_row_count": 2},
                ],
                "source_candidates": ["SelDocManageList"],
                "recommended_capture_strategy": "http_followup_with_action_chain",
                "payload_hints": {"date_fields": ["bdate", "edate"], "enum_fields": ["stat"]},
                "single_variable_probe_results": [],
            }
        ]
    }
    _write(analysis_root / "yeusoft-page-research-20260322-000500.json", json.dumps(page_research, ensure_ascii=False))
    menu_coverage = {
        "summary": {
            "audit_complete": True,
            "all_visible_pages_classified": True,
            "menu_node_count": 3,
            "container_only_count": 0,
            "clickable_page_count": 1,
            "covered_count": 1,
            "visible_but_untracked_count": 0,
            "visible_but_failed_count": 0,
            "unknown_pages": [],
            "unmatched_registry_targets": [],
        },
        "pages": [
            {
                "title": "门店盘点单",
                "page_title": "门店盘点单",
                "menu_path": ["单据管理", "盘点业务", "门店盘点单"],
                "root_name": "单据管理",
                "group_name": "盘点业务",
                "coverage_status": "covered",
                "coverage_confidence": "medium",
                "matched_registry_titles": [],
            }
        ],
        "containers": [],
    }
    _write(analysis_root / "menu-coverage-audit-20260322-000600.json", json.dumps(menu_coverage, ensure_ascii=False))
    _write(
        analysis_root / "store-stocktaking-evidence-chain-20260322-000700.json",
        json.dumps(
            {
                "store_stocktaking": {
                    "capture_parameter_plan": {
                        "stat_seed_values": ["stat=A", "stat=0", "stat=1"],
                        "primary_stat_values": ["A", "1"],
                    },
                    "blocking_issues": [],
                    "secondary_route_blocking_issues": [
                        "查看明细二级接口仍待识别",
                        "统计损溢二级接口仍待识别",
                        "条码记录二级接口仍待识别",
                    ],
                    "capture_admission_ready": True,
                    "judgment": "真实主列表接口已通过 HTTP 回证，当前可稳定返回盘点单主列表；stat=1 与 baseline 当前等价、stat=0 会收窄为空集，日期范围作为边界参数固定后，主列表已可单独准入 capture；查看明细、统计损溢、条码记录应拆成后续二级路线。",
                },
                "conclusion": {
                    "next_focus": "门店盘点单主列表可先按固定 stat/date 窗口准入 capture；继续确认查看明细、条码记录、统计损溢是否拆成独立二级接口。"
                },
            },
            ensure_ascii=False,
        ),
    )

    board = build_api_maturity_board(repo_root, analysis_root)
    routes = {entry["route"]: entry for entry in board["entries"]}

    entry = routes["门店盘点单 / SelDocManageList"]
    assert entry["stage"] == "已HTTP回证"
    assert entry["blocking_issues"] == []
    assert entry["capture_parameter_plan"] == {
        "stat_seed_values": ["stat=A", "stat=0", "stat=1"],
        "primary_stat_values": ["A", "1"],
    }
    assert entry["capture_admission_ready"] is True
    assert entry["secondary_route_blocking_issues"] == [
        "查看明细二级接口仍待识别",
        "统计损溢二级接口仍待识别",
        "条码记录二级接口仍待识别",
    ]
    assert entry["next_action"].startswith("门店盘点单主列表可先按固定 stat/date")


def test_build_api_maturity_board_marks_store_stocktaking_capture_runtime(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"
    analysis_root.mkdir(parents=True)

    empty_ledger = _ledger([])
    _write(repo_root / "docs" / "erp" / "sales-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "member-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", empty_ledger)
    _write(
        repo_root / "docs" / "erp" / "payment-and-doc-ledger.md",
        _ledger(
            [
                (
                    "门店盘点单",
                    "JyApi/EposDoc/SelDocManageList",
                    "当前真实主列表接口已识别并完成 HTTP 回证，stat 与日期范围都会改变数据范围，但查看明细/统计损溢/条码记录的二级动作链仍待识别",
                    "需要补动作链；需要确认正式保留值集",
                    "待识别",
                )
            ]
        ),
    )

    _write(
        analysis_root / "yeusoft-page-research-20260322-000500.json",
        json.dumps(
            {
                "pages": [
                    {
                        "title": "门店盘点单",
                        "status": "ok",
                        "menu_target_title": "门店盘点单",
                        "menu_root_name": "单据管理",
                        "group_name": "盘点业务",
                        "menu_path": ["单据管理", "盘点业务", "门店盘点单"],
                        "target_menu_path": ["单据管理", "盘点业务", "门店盘点单"],
                        "grain_route": "single_route",
                        "endpoint_summaries": [
                            {"endpoint": "SelDocManageList", "is_data_endpoint": True, "max_row_count": 2}
                        ],
                        "source_candidates": ["SelDocManageList"],
                        "recommended_capture_strategy": "http_followup_with_action_chain",
                        "payload_hints": {"date_fields": ["bdate", "edate"], "enum_fields": ["stat"]},
                        "single_variable_probe_results": [],
                    }
                ]
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "menu-coverage-audit-20260322-000600.json",
        json.dumps(
            {
                "summary": {
                    "audit_complete": True,
                    "all_visible_pages_classified": True,
                    "menu_node_count": 3,
                    "container_only_count": 0,
                    "clickable_page_count": 1,
                    "covered_count": 1,
                    "visible_but_untracked_count": 0,
                    "visible_but_failed_count": 0,
                    "unknown_pages": [],
                    "unmatched_registry_targets": [],
                },
                "pages": [
                    {
                        "title": "门店盘点单",
                        "page_title": "门店盘点单",
                        "menu_path": ["单据管理", "盘点业务", "门店盘点单"],
                        "root_name": "单据管理",
                        "group_name": "盘点业务",
                        "coverage_status": "covered",
                        "coverage_confidence": "medium",
                        "matched_registry_titles": [],
                    }
                ],
                "containers": [],
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "store-stocktaking-evidence-chain-20260322-000700.json",
        json.dumps(
            {
                "store_stocktaking": {
                    "capture_parameter_plan": {
                        "baseline_payload": {"menuid": "E003002001"},
                        "stat_seed_values": ["stat=A", "stat=0", "stat=1"],
                        "primary_stat_values": ["A", "1"],
                    },
                    "blocking_issues": [],
                    "secondary_route_blocking_issues": [
                        "查看明细二级接口仍待识别",
                        "统计损溢二级接口仍待识别",
                        "条码记录二级接口仍待识别",
                    ],
                    "capture_admission_ready": True,
                    "judgment": "真实主列表接口已通过 HTTP 回证，当前可稳定返回盘点单主列表；stat=1 与 baseline 当前等价、stat=0 会收窄为空集，日期范围作为边界参数固定后，主列表已可单独准入 capture；查看明细、统计损溢、条码记录应拆成后续二级路线。",
                },
                "conclusion": {
                    "next_focus": "门店盘点单主列表可先按固定 stat/date 窗口准入 capture；继续确认查看明细、条码记录、统计损溢是否拆成独立二级接口。"
                },
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "store-stocktaking-capture-admission-20260322-000710.json",
        json.dumps(
            {
                "capture_batch_id": "stocktaking-batch-001",
                "source_endpoint": "yeusoft.docs.store_stocktaking_list",
            },
            ensure_ascii=False,
        ),
    )

    board = build_api_maturity_board(repo_root, analysis_root)
    entry = {item["route"]: item for item in board["entries"]}["门店盘点单 / SelDocManageList"]

    assert entry["capture_written_once"] is True
    assert entry["latest_capture_batch_id"] == "stocktaking-batch-001"
    assert entry["latest_capture_mode"] == "admission"
    assert entry["mainline_ready"] is True


def test_build_api_maturity_board_applies_store_stocktaking_ui_probe_insight(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"
    analysis_root.mkdir(parents=True)

    empty_ledger = _ledger([])
    _write(repo_root / "docs" / "erp" / "sales-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "member-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", empty_ledger)
    _write(
        repo_root / "docs" / "erp" / "payment-and-doc-ledger.md",
        _ledger(
            [
                (
                    "门店盘点单",
                    "JyApi/EposDoc/SelDocManageList",
                    "当前真实主列表接口已识别并完成 HTTP 回证，stat 与日期范围都会改变数据范围，但查看明细/统计损溢/条码记录的二级动作链仍待识别",
                    "需要补动作链；需要确认正式保留值集",
                    "待识别",
                )
            ]
        ),
    )

    _write(
        analysis_root / "yeusoft-page-research-20260322-000500.json",
        json.dumps(
            {
                "pages": [
                    {
                        "title": "门店盘点单",
                        "status": "ok",
                        "menu_target_title": "门店盘点单",
                        "menu_root_name": "单据管理",
                        "group_name": "盘点业务",
                        "menu_path": ["单据管理", "盘点业务", "门店盘点单"],
                        "target_menu_path": ["单据管理", "盘点业务", "门店盘点单"],
                        "grain_route": "single_route",
                        "endpoint_summaries": [{"endpoint": "SelDocManageList", "is_data_endpoint": True, "max_row_count": 2}],
                        "source_candidates": ["SelDocManageList"],
                        "recommended_capture_strategy": "http_followup_with_action_chain",
                        "payload_hints": {"date_fields": ["bdate", "edate"], "enum_fields": ["stat"]},
                        "single_variable_probe_results": [],
                    }
                ]
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "menu-coverage-audit-20260322-000600.json",
        json.dumps(
            {
                "summary": {
                    "audit_complete": True,
                    "all_visible_pages_classified": True,
                    "menu_node_count": 3,
                    "container_only_count": 0,
                    "clickable_page_count": 1,
                    "covered_count": 1,
                    "visible_but_untracked_count": 0,
                    "visible_but_failed_count": 0,
                    "unknown_pages": [],
                    "unmatched_registry_targets": [],
                },
                "pages": [
                    {
                        "title": "门店盘点单",
                        "page_title": "门店盘点单",
                        "menu_path": ["单据管理", "盘点业务", "门店盘点单"],
                        "root_name": "单据管理",
                        "group_name": "盘点业务",
                        "coverage_status": "covered",
                        "coverage_confidence": "medium",
                        "matched_registry_titles": [],
                    }
                ],
                "containers": [],
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "store-stocktaking-evidence-chain-20260322-000700.json",
        json.dumps(
            {
                "store_stocktaking": {
                    "capture_parameter_plan": {"baseline_payload": {"menuid": "E003002001"}},
                    "blocking_issues": [],
                    "secondary_route_blocking_issues": [
                        "查看明细二级接口仍待识别",
                        "统计损溢二级接口仍待识别",
                        "条码记录二级接口仍待识别",
                    ],
                    "capture_admission_ready": True,
                    "judgment": "主列表已可准入，二级动作链待补。",
                },
                "conclusion": {"next_focus": "先补二级动作链。"},
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "store-stocktaking-ui-probe-20260324-000537.json",
        json.dumps(
            {
                "component_method_probes": [
                    {
                        "key": "component_method_getDiffData",
                        "local_state_after": {
                            "snapshot": {
                                "showDiffPage": False,
                                "orderDiffData": {"length": 20},
                                "orderDiffHJData": {"length": 2},
                            }
                        },
                    },
                    {
                        "key": "component_method_getDetailList",
                        "local_state_after": {
                            "snapshot": {
                                "showDetailPage": False,
                                "orderDetailData": {"length": 0},
                            }
                        },
                    },
                ]
            },
            ensure_ascii=False,
        ),
    )

    board = build_api_maturity_board(repo_root, analysis_root)
    entry = {item["route"]: item for item in board["entries"]}["门店盘点单 / SelDocManageList"]

    assert entry["observed_local_secondary_state"] == {
        "order_diff_rows": 20,
        "order_diff_summary_rows": 2,
        "order_detail_rows": 0,
        "show_diff_page": False,
        "show_detail_page": False,
    }
    assert "统计损溢已能本地填充 orderDiffData，但尚未确认是独立 HTTP route 还是本地派生数据" in entry[
        "secondary_route_blocking_issues"
    ]
    assert entry["next_action"].startswith("门店盘点单主列表已可准入 capture；下一步应优先确认 getDiffData(row)")


def test_build_api_maturity_board_adds_store_stocktaking_diff_secondary_route(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"

    for relative in (
        "docs/erp/sales-ledger.md",
        "docs/erp/inventory-ledger.md",
        "docs/erp/member-ledger.md",
        "docs/erp/stored-value-ledger.md",
    ):
        _write(repo_root / relative, _ledger([]))
    _write(
        repo_root / "docs" / "erp" / "payment-and-doc-ledger.md",
        _ledger([("门店盘点单", "JyApi/EposDoc/SelDocManageList", "主列表候选", "需要翻页", "单请求")]),
    )

    _write(
        analysis_root / "yeusoft-page-research-20260324-000000.json",
        json.dumps(
            {
                "pages": [
                    {
                        "title": "门店盘点单",
                        "status": "ok",
                        "grain_route": "single_route",
                        "menu_path": ["单据管理", "盘点业务", "门店盘点单"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "menu-coverage-audit-20260324-000000.json",
        json.dumps(
            {
                "summary": {
                    "audit_complete": True,
                    "all_visible_pages_classified": True,
                    "visible_but_untracked_count": 0,
                },
                "pages": [
                    {
                        "title": "门店盘点单",
                        "page_title": "门店盘点单",
                        "menu_path": ["单据管理", "盘点业务", "门店盘点单"],
                        "root_name": "单据管理",
                        "coverage_status": "covered",
                        "coverage_confidence": "high",
                    }
                ],
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "store-stocktaking-ui-probe-20260324-000001.json",
        json.dumps(
            {
                "component_method_probes": [
                    {
                        "key": "component_method_getDiffData",
                        "local_state_after": {
                            "snapshot": {
                                "showDiffPage": False,
                                "orderDiffData": {
                                    "type": "array",
                                    "length": 2,
                                    "full_rows": [
                                        {"PdID": "PD0001", "SpeNum": "SKU-1"},
                                        {"PdID": "PD0001", "SpeNum": "SKU-2"},
                                    ],
                                },
                                "orderDiffHJData": {
                                    "type": "array",
                                    "length": 1,
                                    "full_rows": [{"SpeNum": "合计"}],
                                },
                            }
                        },
                    },
                    {
                        "key": "component_method_getDiffData_row_1",
                        "component_invocation": {
                            "selected_row": {"PdID": "PD0001", "SpeNum": "SKU-2"},
                        },
                        "local_state_after": {
                            "snapshot": {
                                "orderDiffData": {
                                    "type": "array",
                                    "length": 0,
                                },
                                "orderDiffHJData": {
                                    "type": "array",
                                    "length": 0,
                                },
                            }
                        },
                    },
                    {
                        "key": "component_method_getDiffData_row_2",
                        "component_invocation": {
                            "selected_row": None,
                        },
                        "local_state_after": {
                            "snapshot": {
                                "orderDiffData": {
                                    "type": "array",
                                    "length": 0,
                                },
                                "orderDiffHJData": {
                                    "type": "array",
                                    "length": 0,
                                },
                            }
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
    )

    board = build_api_maturity_board(repo_root, analysis_root)

    entry = {item["route"]: item for item in board["entries"]}["门店盘点单 / store_stocktaking_diff_records"]
    assert entry["role"] == "研究留痕"
    assert entry["stage"] == "已单变量"
    assert entry["observed_local_secondary_state"] == {
        "order_diff_rows": 2,
        "order_diff_summary_rows": 1,
        "show_diff_page": False,
        "row_1_order_diff_rows": 0,
        "row_2_order_diff_rows": 0,
    }
    assert "统计损溢当前更像本地派生数据" in " ".join(entry["blocking_issues"])
    assert "按行调用 getDiffData(row_1) 当前会把 diff 状态清空" in " ".join(entry["blocking_issues"])
    assert "按行调用 getDiffData(row_2) 当前仍未拿到稳定选中行" in " ".join(entry["blocking_issues"])
    assert entry["capture_parameter_plan"]["multi_row_supported"] is False


def test_build_api_maturity_board_marks_receipt_confirmation_capture_runtime(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"
    analysis_root.mkdir(parents=True)

    empty_ledger = _ledger([])
    _write(repo_root / "docs" / "erp" / "sales-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "member-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", empty_ledger)
    _write(
        repo_root / "docs" / "erp" / "payment-and-doc-ledger.md",
        _ledger(
            [
                (
                    "收货确认",
                    "JyApi/EposDoc/SelDocConfirmList",
                    "当前真实主接口已识别并完成 HTTP 回证，但 seed 参数仍未改变数据集，疑似依赖隐藏页面上下文或选中行动作链",
                    "需要补页面动作链；需要确认全量边界",
                    "待识别",
                )
            ]
        ),
    )

    _write(
        analysis_root / "yeusoft-page-research-20260322-000500.json",
        json.dumps(
            {
                "pages": [
                    {
                        "title": "收货确认",
                        "status": "ok",
                        "menu_target_title": "收货确认",
                        "menu_root_name": "单据管理",
                        "group_name": "上级往来",
                        "menu_path": ["单据管理", "上级往来", "收货确认"],
                        "target_menu_path": ["单据管理", "上级往来", "收货确认"],
                        "grain_route": "single_route",
                        "endpoint_summaries": [
                            {"endpoint": "SelDocConfirmList", "is_data_endpoint": True, "max_row_count": 2}
                        ],
                        "source_candidates": ["SelDocConfirmList"],
                        "recommended_capture_strategy": "http_followup_with_action_chain",
                        "payload_hints": {},
                        "single_variable_probe_results": [],
                    }
                ]
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "menu-coverage-audit-20260322-000600.json",
        json.dumps(
            {
                "summary": {
                    "audit_complete": True,
                    "all_visible_pages_classified": True,
                    "menu_node_count": 3,
                    "container_only_count": 0,
                    "clickable_page_count": 1,
                    "covered_count": 1,
                    "visible_but_untracked_count": 0,
                    "visible_but_failed_count": 0,
                    "unknown_pages": [],
                    "unmatched_registry_targets": [],
                },
                "pages": [
                    {
                        "title": "收货确认",
                        "page_title": "收货确认",
                        "menu_path": ["单据管理", "上级往来", "收货确认"],
                        "root_name": "单据管理",
                        "group_name": "上级往来",
                        "coverage_status": "covered",
                        "coverage_confidence": "medium",
                        "matched_registry_titles": [],
                    }
                ],
                "containers": [],
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "receipt-confirmation-evidence-chain-20260322-000700.json",
        json.dumps(
            {
                "receipt_confirmation": {
                    "capture_parameter_plan": {
                        "baseline_payload": {},
                        "page_seed_values": ["page=1,pagesize=20"],
                        "page_mode": "single_request_same_dataset_verified",
                    },
                    "blocking_issues": [],
                    "secondary_route_blocking_issues": [
                        "单据确认动作链仍依赖页面选中行或隐藏动作链",
                        "物流信息动作链仍依赖页面选中行或隐藏动作链",
                        "扫描校验动作链仍待识别",
                    ],
                    "capture_admission_ready": True,
                    "judgment": "真实主接口已通过 HTTP 回证；当前 seed 参数 page/pageSize/time/search 均未改变数据集，说明主列表可先按空 payload 准入 capture，而单据确认 / 物流信息 / 扫描校验应拆成后续二级动作链。",
                },
                "conclusion": {
                    "next_focus": "收货确认主列表可先按空 payload 准入 capture；继续验证页面选中行和详情/确认动作链是否会补充隐藏参数或明细接口。"
                },
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "receipt-confirmation-capture-admission-20260322-000710.json",
        json.dumps(
            {
                "capture_batch_id": "receipt-batch-001",
                "source_endpoint": "yeusoft.docs.receipt_confirmation_list",
            },
            ensure_ascii=False,
        ),
    )

    board = build_api_maturity_board(repo_root, analysis_root)
    entry = {item["route"]: item for item in board["entries"]}["收货确认 / SelDocConfirmList"]

    assert entry["capture_written_once"] is True
    assert entry["latest_capture_batch_id"] == "receipt-batch-001"
    assert entry["latest_capture_mode"] == "admission"
    assert entry["mainline_ready"] is True


def test_build_api_maturity_board_applies_receipt_confirmation_ui_probe_insight(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"
    analysis_root.mkdir(parents=True)

    empty_ledger = _ledger([])
    _write(repo_root / "docs" / "erp" / "sales-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "inventory-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "member-ledger.md", empty_ledger)
    _write(repo_root / "docs" / "erp" / "stored-value-ledger.md", empty_ledger)
    _write(
        repo_root / "docs" / "erp" / "payment-and-doc-ledger.md",
        _ledger(
            [
                (
                    "收货确认",
                    "JyApi/EposDoc/SelDocConfirmList",
                    "主列表已 admit；二级动作链仍待确认",
                    "待识别",
                    "待识别",
                )
            ]
        ),
    )

    _write(
        analysis_root / "yeusoft-page-research-20260322-000500.json",
        json.dumps(
            {
                "pages": [
                    {
                        "title": "收货确认",
                        "status": "ok",
                        "menu_target_title": "收货确认",
                        "menu_root_name": "单据管理",
                        "group_name": "上级往来",
                        "menu_path": ["单据管理", "上级往来", "收货确认"],
                        "target_menu_path": ["单据管理", "上级往来", "收货确认"],
                        "grain_route": "single_route",
                        "endpoint_summaries": [
                            {"endpoint": "SelDocConfirmList", "is_data_endpoint": True, "max_row_count": 2}
                        ],
                        "source_candidates": ["SelDocConfirmList"],
                        "recommended_capture_strategy": "http_followup_with_action_chain",
                        "payload_hints": {},
                        "single_variable_probe_results": [],
                    }
                ]
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "menu-coverage-audit-20260322-000600.json",
        json.dumps(
            {
                "summary": {
                    "audit_complete": True,
                    "all_visible_pages_classified": True,
                    "menu_node_count": 3,
                    "container_only_count": 0,
                    "clickable_page_count": 1,
                    "covered_count": 1,
                    "visible_but_untracked_count": 0,
                    "visible_but_failed_count": 0,
                    "unknown_pages": [],
                    "unmatched_registry_targets": [],
                },
                "pages": [
                    {
                        "title": "收货确认",
                        "page_title": "收货确认",
                        "menu_path": ["单据管理", "上级往来", "收货确认"],
                        "root_name": "单据管理",
                        "group_name": "上级往来",
                        "coverage_status": "covered",
                        "coverage_confidence": "medium",
                        "matched_registry_titles": [],
                    }
                ],
                "containers": [],
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "receipt-confirmation-evidence-chain-20260322-000700.json",
        json.dumps(
            {
                "receipt_confirmation": {
                    "capture_parameter_plan": {
                        "baseline_payload": {},
                        "page_mode": "single_request_same_dataset_verified",
                    },
                    "blocking_issues": [],
                    "secondary_route_blocking_issues": [
                        "单据确认动作链仍依赖页面选中行或隐藏动作链",
                        "物流信息动作链仍依赖页面选中行或隐藏动作链",
                        "扫描校验动作链仍待识别",
                    ],
                    "capture_admission_ready": True,
                    "judgment": "主列表已可 admit，二级动作链待补。",
                },
                "conclusion": {
                    "next_focus": "收货确认主列表可先按空 payload 准入 capture；继续验证页面选中行和详情/确认动作链。"
                },
            },
            ensure_ascii=False,
        ),
    )
    _write(
        analysis_root / "receipt-confirmation-ui-probe-20260324-010818.json",
        json.dumps(
                {
                    "baseline": {
                        "component_store_after_query": {
                            "store_state_snapshot": {"cleardata": False},
                            "root_data_snapshot": {},
                        },
                        "component_global_storage_after_query": {
                            "local_storage_entries": [],
                            "session_storage_entries": [],
                            "window_snapshot": {
                                "document": {"type": "object", "keys": ["location"]},
                            },
                            "vm_inject_snapshot": {
                                "selectItem": {"type": "array", "length": 0},
                                "CheckList": {"type": "array", "length": 0},
                                "orderDetailHJData": {"type": "array", "length": 0},
                                "orderDetailData": {"type": "array", "length": 0},
                                "orderHJData": {"type": "array", "length": 0},
                                "orderData": {"type": "array", "length": 0},
                                "detailData": {"type": "object", "keys": ["currentItem", "pager"]},
                            },
                        },
                        "component_injection_context_after_query": {
                            "detail_data_snapshot": {
                                "currentItem": None,
                                "keyword": "",
                                "columnType": False,
                                "pager": {"page": 1, "pageSize": 20, "total": 0},
                                "extraHeaderLabels": {"type": "array", "length": 3, "first_row": "数量"},
                                "extraHeader": {"type": "array", "length": 0, "first_row": None},
                                "baseHeaders": {"type": "array", "length": 15, "first_row": {"key": "Index"}},
                                "totalLines": {"type": "array", "length": 0, "first_row": None},
                            },
                            "shell_context": {
                                "menuItemId": {"CheckDoc": "E003001001"},
                                "editableTabs": {
                                    "type": "array",
                                    "length": 1,
                                    "sample_rows": [{"FuncUrl": "CheckDoc", "FuncName": "收货确认"}],
                                },
                            },
                            "root_event_hub": {
                                "keys": ["_uid", "_events", "_data"],
                                "event_keys": [],
                            },
                        },
                        "component_method_sources": {
                            "methods": {
                                "getDataList": {"preview": "function () { [native code] }"},
                                "checkDetail": {"preview": "function () { [native code] }"},
                                "getDetailData": {"preview": "function () { [native code] }"},
                                "LogisticInfoClick": {"preview": "function () { [native code] }"},
                                "tableSelectClick": {"preview": "function () { [native code] }"},
                                "selectionChange": {"preview": "function () { [native code] }"},
                            }
                        },
                        "local_state_after_query": {
                            "snapshot": {
                                "total": 300,
                            "page": 1,
                            "pageSize": 20,
                            "orderData": {"length": 0},
                            "orderDetailData": {"length": 0},
                            "selectItem": {"length": 0},
                            },
                            "nested_table_length": 0,
                        },
                        "component_ancestry_after_query": [
                            {
                                "depth": 0,
                                "props_data_snapshot": {"menuId": "E003001001"},
                                "nested_snapshots": {
                                    "detailData": {"currentItem": None},
                                },
                            },
                            {
                                "depth": 1,
                                "snapshot": {
                                    "menuItemId": {"type": "object", "keys": ["CheckDoc"]},
                                },
                                "nested_snapshots": {
                                    "menuItemId": {"CheckDoc": "E003001001"},
                                },
                                "non_empty_collections": [
                                    {"field": "vipInfoList"},
                                    {"field": "reportLists"},
                                ],
                            },
                        ],
                        "component_ancestry_method_sources_after_query": [
                            {
                                "depth": 0,
                                "methods": [
                                    {"name": "getDataList", "preview": "function () { [native code] }"},
                                    {"name": "checkDetail", "preview": "function () { [native code] }"},
                                ],
                            },
                            {
                                "depth": 1,
                                "methods": [
                                    {"name": "GetMenuList", "preview": "function () { [native code] }"},
                                    {"name": "jumpPage", "preview": "function () { [native code] }"},
                                ],
                            },
                        ],
                    },
                    "component_method_probes": [
                    {
                        "key": "component_method_getDataList",
                        "request_diffs": [{"endpoint": "SelDocConfirmList"}],
                        "local_state_after": {
                            "snapshot": {
                                "orderData": {"length": 0},
                                "orderDetailData": {"length": 0},
                            }
                        },
                    },
                    {
                        "key": "component_method_tableSelectClick",
                        "local_state_after": {"snapshot": {"selectItem": {"length": 0}}},
                        "nested_row_context_after": {"table_length": 0},
                    },
                    {
                        "key": "component_method_selectionChange",
                        "local_state_after": {"snapshot": {"selectItem": {"length": 0}}},
                        "nested_row_context_after": {"table_length": 0},
                    },
                ],
                "ref_method_probes": [
                    {
                        "key": "ref_method_reportTableItem_mainRef_RTM_searchConditions",
                        "request_diffs": [],
                        "local_state_after": {
                            "snapshot": {
                                "orderData": {"length": 0},
                                "selectItem": {"length": 0},
                            }
                        },
                        "ref_state_after": {
                            "child_refs": {
                                "RTM_reportTable": {
                                    "snapshot": {
                                        "tablePage": {"type": "object", "keys": ["total", "currentPage", "pageSize"]}
                                    }
                                }
                            }
                        },
                    },
                    {
                        "key": "ref_method_reportTableItem_mainRef_RTM_toggleCheckboxRow",
                        "request_diffs": [],
                        "local_state_after": {
                            "snapshot": {
                                "orderData": {"length": 0},
                                "selectItem": {"length": 0},
                            }
                        },
                        "ref_state_after": {
                            "child_refs": {
                                "RTM_reportTable": {
                                    "snapshot": {
                                        "tablePage": {"type": "object", "keys": ["total", "currentPage", "pageSize"]}
                                    }
                                }
                            }
                        },
                    },
                    {
                        "key": "ref_method_reportTableItem_mainRef_RTM_GetViewGridHead",
                        "request_diffs": [{"endpoint": "GetViewGridList"}],
                        "local_state_after": {
                            "snapshot": {
                                "orderData": {"length": 0},
                                "selectItem": {"length": 0},
                            }
                        },
                    },
                    {
                        "key": "ref_method_reportTableItem_mainRef_RTM_getTableHeader",
                        "request_diffs": [],
                        "local_state_after": {
                            "snapshot": {
                                "orderData": {"length": 0},
                                "selectItem": {"length": 0},
                            }
                        },
                    },
                ],
                "ref_method_sources": [
                    {
                        "methods": {
                            "RTM_searchConditions": {"preview": "function () { [native code] }"},
                            "RTM_toggleCheckboxRow": {"preview": "function () { [native code] }"},
                        }
                    }
                ],
                "child_ref_method_sources": [
                    {
                        "methods": {
                            "searchDataInfo": {"preview": "function () { [native code] }"},
                            "tableDataInit": {"preview": "function () { [native code] }"},
                            "finishViewData": {"preview": "function () { [native code] }"},
                            "vxeGirdLoadData": {"preview": "function () { [native code] }"},
                        }
                    }
                ],
                "child_ref_method_probes": [
                    {
                        "key": "child_ref_method_reportTableItem_mainRef_RTM_reportTable_searchConditions",
                        "request_diffs": [],
                        "local_state_after": {
                            "snapshot": {
                                "orderData": {"length": 0},
                                "selectItem": {"length": 0},
                            }
                        },
                        "child_ref_state_after": {
                            "snapshot": {
                                "tablePage": {"type": "object", "keys": ["total", "currentPage", "pageSize"]}
                            }
                        },
                    },
                    {
                        "key": "child_ref_method_reportTableItem_mainRef_RTM_reportTable_searchDataInfo",
                        "request_diffs": [],
                        "local_state_after": {
                            "snapshot": {
                                "orderData": {"length": 0},
                                "selectItem": {"length": 0},
                            }
                        },
                        "child_ref_state_after": {
                            "snapshot": {
                                "tablePage": {"type": "object", "keys": ["total", "currentPage", "pageSize"]},
                                "allTableData": {"length": 0},
                                "vxeTable": {"keys": ["tableData", "database"]},
                            },
                            "special_snapshot": {
                                "props_keys": ["tableAttrs", "tableData", "showFooter", "databaseTableName"],
                                "props_data_keys": ["tableAttrs", "showFooter", "databaseTableName"],
                                "allTableData": {"length": 0},
                                "tableData": {"length": 0},
                                "vxeTable_snapshot": {
                                    "tableData": {"length": 0},
                                    "viewData": {"length": 0},
                                    "initHeaderData": {"length": 0},
                                    "database": {
                                        "keys": ["dbId", "DateBaseName", "Version", "Description", "DataBaseSize", "browser"]
                                    },
                                },
                            },
                        },
                        "child_ref_indexeddb_after": {
                            "database_name": "FXDATABASE",
                            "database_table_name": "receiveConfirm_E003001001_1",
                            "target_database": {
                                "object_store_names": [],
                                "target_store": None,
                            },
                        },
                    },
                    {
                        "key": "child_ref_method_reportTableItem_mainRef_RTM_reportTable_tableDataInit",
                        "request_diffs": [],
                        "child_ref_state_after": {
                            "snapshot": {
                                "loading": True,
                                "tableColumn": {"length": 6},
                                "allTableData": {"length": 0},
                                "vxeTable": {"keys": ["tableData"]},
                            }
                        },
                    },
                    {
                        "key": "child_ref_method_reportTableItem_mainRef_RTM_reportTable_finishViewData",
                        "request_diffs": [],
                        "child_ref_state_after": {
                            "snapshot": {
                                "loading": True,
                                "tableColumn": {"length": 6},
                                "allTableData": {"length": 0},
                                "vxeTable": {"keys": ["tableData"]},
                            }
                        },
                    },
                ],
            },
            ensure_ascii=False,
        ),
    )

    board = build_api_maturity_board(repo_root, analysis_root)
    entry = {item["route"]: item for item in board["entries"]}["收货确认 / SelDocConfirmList"]

    assert "receipt-confirmation-ui-probe-20260324-010818.json" in "\n".join(entry["analysis_sources"])
    assert set(entry["secondary_route_blocking_issues"]) == {
        "单据确认动作链仍依赖页面选中行或隐藏动作链",
        "物流信息动作链仍依赖页面选中行或隐藏动作链",
        "扫描校验动作链仍待识别",
        "receiveConfirm 组件已出现 total/page/pageSize，但 orderData/orderDetailData/selectItem 与嵌套表格持续为空",
        "receiveConfirm 父链上一层目前只见 menuItemId.CheckDoc 与壳层 tab/menu 集合，未见任何上游订单行缓存",
        "receiveConfirm.menuId 与父链 menuItemId.CheckDoc 当前同值，但 detailData.currentItem 仍为空，说明列表上下文并未继续注入到详情层",
        "getDataList 只会重发 SelDocConfirmList，仍未填充 orderData/orderDetailData",
        "tableSelectClick/selectionChange 当前不会建立稳定选中态，也未填充 selectItem/currentRow",
        "reportTableItem_mainRef.$refs.RTM_reportTable 已暴露 tablePage，但仍没有任何行数据",
        "reportTableItem_mainRef.RTM_GetViewGridHead 只会重发 GetViewGridList，说明表头链存在但行数据链仍未建立",
        "RTM_reportTable.searchConditions/searchDataInfo/pageCondition/GetTotalData/allPageSelect 已可调用，但仍完全 no-op",
        "RTM_reportTable 已暴露 tableColumn，但 allTableData/vxeTable.tableData 仍为空，说明子表结构已建而源数据数组仍未注入",
        "RTM_reportTable.tableDataInit/finishViewData 可调用且会切 loading，但仍未生成任何 tableData/allTableData",
        "RTM_reportTable 已声明 tableData 等输入能力，但 propsData 当前只传 databaseTableName/showFooter 等视图参数，未传任何数据集",
        "RTM_reportTable.vxeTable.database 当前只见本地库元信息，tableData/viewData/initHeaderData 仍全空，说明缺的是更早的源数据注入",
        "RTM_reportTable.vxeTable.database 已指向 FXDATABASE，但浏览器实际打开后 object_store_names 为空，receiveConfirm_E003001001_1 并未落成本地表",
        "receiveConfirm.$store.state 当前只见 cleardata 标志，未见任何订单/详情缓存",
        "receiveConfirm.$root._data 当前未见任何订单/详情缓存字段",
        "receiveConfirm vm 注入字段已存在，但 orderData/orderDetailData/orderHJData/selectItem/CheckList 仍全为空，detailData 也还只是壳对象",
        "receiveConfirm 根层 total=300，但 detailData.pager.total 仍为 0，说明详情层分页上下文尚未承接主列表数据",
        "父链 editableTabs 当前只保留 FuncUrl/FuncName 壳层 tab 元信息，未见任何附加数据载荷",
        "根层 yisEventHub 已存在但 _events 为空，未见通过事件总线注入明细数据的迹象",
        "receiveConfirm.getDataList/checkDetail/getDetailData/LogisticInfoClick 等关键方法源码当前都只暴露 native code 包装，已无法继续从根组件函数体反推注入链",
        "receiveConfirm 父链壳层方法当前也只暴露 native code 包装，说明更早的菜单/页面注入链同样不可从函数体继续回溯",
        "reportTableItem_mainRef 与 RTM_reportTable 的关键方法源码当前都只暴露 native code 包装，已无法继续从函数体反推初始化链",
    }
    assert entry["next_action"].startswith("收货确认主列表已 admit；下一步应沿 receiveConfirm.menuId、父链 menuItemId.CheckDoc 与 detailData.currentItem")
    assert "FXDATABASE" in entry["next_action"]
