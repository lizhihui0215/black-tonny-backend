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
        _ledger([("库存明细统计", "YisEposReport/SelDeptStockWaitList", "当前最像库存事实源候选", "需要翻页", "自动翻页")]),
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
                "title": "会员中心",
                "status": "ok",
                "grain_route": "single_route",
                "endpoint_summaries": [{"endpoint": "SelVipInfoList"}],
            },
        ]
    }
    _write(analysis_root / "yeusoft-page-research-20260322-000100.json", json.dumps(page_research, ensure_ascii=False))

    sales_evidence = {
        "issue_flags": [
            "edate 当前未收口到正式 HTTP 主链参数",
            "对账指标 line_count 仍是差异待解释",
        ],
        "join_key_analysis": {
            "candidate_keys": [
                {"key": "sale_no", "stable_candidate": True},
                {"key": "sale_date", "stable_candidate": False},
                {"key": "operator", "stable_candidate": False},
                {"key": "vip_card_no", "stable_candidate": True},
            ]
        },
    }
    _write(analysis_root / "sales-evidence-chain-20260322-000200.json", json.dumps(sales_evidence, ensure_ascii=False))
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
    assert routes["SelDeptSaleList"]["role"] == "对账源"
    assert routes["库存明细统计 / SelDeptStockWaitList"]["stage"] == "已单变量"
    assert routes["库存明细统计 / SelDeptStockWaitList"]["next_action"] == "确认 stockflag=1/2 的正式抓取策略，并补分页终止规则"
    assert routes["会员中心 / SelVipInfoList"]["blocking_issues"] == [
        "condition / searchval / VolumeNumber 语义仍待确认",
        "尚未完成纯 HTTP 回证",
    ]
    assert "未知销售页面 / unknown_page_needs_baseline" in routes
    assert routes["未知销售页面 / unknown_page_needs_baseline"]["source_kind"] == "待识别"
    assert routes["未知销售页面 / unknown_page_needs_baseline"]["coverage_status"] == "visible_but_untracked"
    assert board["summary"]["research_map_complete_count"] == 5
    assert board["summary"]["menu_coverage_audit_complete"] is True
    assert board["summary"]["global_risk_map_complete"] is False
    assert board["summary"]["menu_coverage"]["visible_but_untracked_count"] == 1
    assert board["summary"]["total_routes"] == 8


def test_render_api_maturity_board_markdown_includes_status_sections():
    board = {
        "summary": {
            "total_routes": 1,
            "mainline_ready_count": 0,
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
            "top_blockers": [{"issue": "对账指标 line_count 仍是差异待解释", "count": 1}],
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
                "blocking_issues": ["对账指标 line_count 仍是差异待解释"],
                "next_action": "继续收口 line_count",
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
    assert "对账指标 line_count 仍是差异待解释" in markdown


def test_build_api_maturity_board_promotes_researched_unknown_pages_into_real_routes(tmp_path: Path):
    repo_root = tmp_path / "repo"
    analysis_root = repo_root / "tmp" / "capture-samples" / "analysis"

    empty_ledger = _ledger([])
    _write(repo_root / "docs" / "erp" / "sales-ledger.md", empty_ledger)
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
                "endpoint_summaries": [{"endpoint": "SelWareInfoList", "is_data_endpoint": True, "max_row_count": 120}],
                "source_candidates": ["SelWareInfoList"],
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
    assert "商品资料 / SelWareInfoList" in routes
    assert routes["商品资料 / SelWareInfoList"]["source_kind"] == "主源候选"
    assert routes["商品资料 / SelWareInfoList"]["stage"] == "已基线"
    assert routes["商品资料 / SelWareInfoList"]["coverage_status"] == "covered"
    assert routes["参数设置 / GetViewGridList"]["source_kind"] == "未采纳"
    assert routes["参数设置 / GetViewGridList"]["blocking_issues"] == ["配置/设置类页面，默认不进入事实主链"]
    assert board["summary"]["menu_coverage"]["visible_but_untracked_count"] == 0
    assert board["summary"]["global_risk_map_complete"] is True
    assert not any("unknown_page_needs_baseline" in route for route in routes)
