from __future__ import annotations

import json
from pathlib import Path

from app.services.api_maturity_board_service import (
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
            "capture_admission_ready": False,
            "blocking_issues": [
                "condition 语义仍待确认",
                "VolumeNumber 的业务语义仍待命名",
                "是否存在服务端上限仍待确认",
            ],
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
        }
    }
    _write(analysis_root / "member-evidence-chain-20260322-000260.json", json.dumps(member_evidence, ensure_ascii=False))
    _write(
        analysis_root / "member-capture-research-20260322-000262.json",
        json.dumps({"capture_batch_id": "member-batch-001"}, ensure_ascii=False),
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
    assert routes["库存明细统计 / SelDeptStockWaitList"]["next_action"] == "库存明细统计已具备 capture 候选准入条件，按 stockflag=0/1 双范围留痕并固定 page=0"
    assert routes["出入库单据 / SelOutInStockReport"]["stage"] == "已HTTP回证"
    assert routes["出入库单据 / SelOutInStockReport"]["capture_admission_ready"] is False
    assert routes["出入库单据 / SelOutInStockReport"]["recommended_doctype_values"] == ["1", "2", "3", "7"]
    assert routes["出入库单据 / SelOutInStockReport"]["capture_written_once"] is True
    assert routes["出入库单据 / SelOutInStockReport"]["latest_capture_batch_id"] == "inventory-outin-batch-001"
    assert routes["会员中心 / SelVipInfoList"]["stage"] == "已HTTP回证"
    assert routes["会员中心 / SelVipInfoList"]["capture_admission_ready"] is False
    assert routes["会员中心 / SelVipInfoList"]["blocking_issues"] == [
        "condition 语义仍待确认",
        "VolumeNumber 的业务语义仍待命名",
        "是否存在服务端上限仍待确认",
    ]
    assert routes["会员中心 / SelVipInfoList"]["capture_parameter_plan"]["default_condition"] == ""
    assert routes["会员中心 / SelVipInfoList"]["capture_written_once"] is True
    assert routes["会员中心 / SelVipInfoList"]["latest_capture_batch_id"] == "member-batch-001"
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
    assert entry["next_action"] == "先确认 SelReturnStockList 的 type 参数和页面附加参数，再定位 SQL 截断边界"


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
                    "capture_parameter_plan": {"type_seed_values": ["0", "1", "2", "3"]},
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
    assert entry["capture_parameter_plan"] == {"type_seed_values": ["0", "1", "2", "3"]}
    assert entry["blocking_issues"] == [
        "当前 seed type 值全部触发服务端错误",
        "服务端 SQL 截断错误仍未解除",
        "尚未确认可稳定返回数据的 type 取值",
    ]
