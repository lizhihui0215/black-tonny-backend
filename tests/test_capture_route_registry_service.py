from __future__ import annotations

from app.services.capture_route_registry_service import (
    build_capture_route_registry_from_board,
    render_capture_route_registry_markdown,
)


def test_build_capture_route_registry_marks_sales_routes_and_exclusions() -> None:
    board = {
        "summary": {"global_risk_map_complete": True},
        "entries": [
            {
                "domain": "sales",
                "domain_label": "销售",
                "route": "SelSaleReport",
                "title": "销售清单",
                "endpoint": "SelSaleReport",
                "menu_path": ["报表管理", "零售报表", "销售清单"],
                "source_kind": "主源候选",
                "stage": "已HTTP回证",
                "reliability_status": "中等可信",
                "research_map_complete": True,
                "mainline_ready": False,
                "blocking_issues": [],
                "next_action": "准备首批 capture 准入",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_written_once": True,
                "latest_capture_batch_id": "sales-batch-001",
                "latest_capture_mode": "admission",
                "latest_capture_artifact": "tmp/capture-samples/analysis/sales-capture-admission-20260322-000205.json",
            },
            {
                "domain": "sales",
                "domain_label": "销售",
                "route": "GetDIYReportData(E004001008_2)",
                "title": "销售清单",
                "endpoint": "GetDIYReportData",
                "menu_path": ["报表管理", "零售报表", "销售清单"],
                "source_kind": "主源候选",
                "stage": "已HTTP回证",
                "reliability_status": "中等可信",
                "research_map_complete": True,
                "mainline_ready": False,
                "blocking_issues": [],
                "next_action": "准备首批 capture 准入",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_written_once": True,
                "latest_capture_batch_id": "sales-batch-001",
                "latest_capture_mode": "admission",
                "latest_capture_artifact": "tmp/capture-samples/analysis/sales-capture-admission-20260322-000205.json",
            },
            {
                "domain": "sales",
                "domain_label": "销售",
                "route": "sales_reverse_document_lines",
                "title": "sales_reverse_document_lines",
                "endpoint": "sales_reverse_document_lines",
                "menu_path": ["报表管理", "零售报表", "销售清单"],
                "source_kind": "研究留痕",
                "stage": "已HTTP回证",
                "reliability_status": "中等可信",
                "research_map_complete": True,
                "mainline_ready": False,
                "blocking_issues": [],
                "next_action": "继续保持 capture 研究留痕",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_written_once": True,
                "latest_capture_batch_id": "sales-batch-001",
                "latest_capture_mode": "research",
                "latest_capture_artifact": "tmp/capture-samples/analysis/sales-capture-admission-20260322-000205.json",
            },
            {
                "domain": "inventory",
                "domain_label": "库存",
                "route": "库存明细统计 / SelDeptStockWaitList",
                "title": "库存明细统计",
                "endpoint": "SelDeptStockWaitList",
                "menu_path": ["报表管理", "库存报表", "库存明细统计"],
                "source_kind": "主源候选",
                "stage": "已HTTP回证",
                "reliability_status": "中等可信",
                "research_map_complete": True,
                "mainline_ready": False,
                "blocking_issues": [],
                "next_action": "准备库存 capture 准入",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_parameter_plan": {"stockflag_values": ["0", "1"], "page_mode": "fixed_page_zero"},
                "capture_written_once": True,
                "latest_capture_batch_id": "inventory-stock-batch-001",
                "latest_capture_mode": "admission",
                "latest_capture_artifact": "tmp/capture-samples/analysis/inventory-stock-capture-admission-20260322-000255.json",
            },
            {
                "domain": "member",
                "domain_label": "会员",
                "route": "会员中心 / SelVipInfoList",
                "title": "会员中心",
                "endpoint": "SelVipInfoList",
                "menu_path": ["会员资料", "会员中心"],
                "source_kind": "主源候选",
                "stage": "已HTTP回证",
                "reliability_status": "中等可信",
                "research_map_complete": True,
                "mainline_ready": False,
                "blocking_issues": ["condition 语义仍待确认"],
                "next_action": "继续反推 condition 合法值",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_parameter_plan": {"default_condition": "", "default_searchval": ""},
                "capture_written_once": True,
                "latest_capture_batch_id": "member-batch-001",
                "latest_capture_mode": "research",
                "latest_capture_artifact": "tmp/capture-samples/analysis/member-capture-research-20260322-000262.json",
            },
            {
                "domain": "sales",
                "domain_label": "销售",
                "route": "参数设置 / page_baseline",
                "title": "参数设置",
                "endpoint": "page_baseline",
                "menu_path": ["其他", "参数设置"],
                "source_kind": "未采纳",
                "stage": "已基线",
                "reliability_status": "能跑但不能信",
                "research_map_complete": True,
                "mainline_ready": False,
                "blocking_issues": ["配置页面"],
                "next_action": "不进入 capture",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_written_once": False,
                "latest_capture_batch_id": None,
                "latest_capture_mode": None,
                "latest_capture_artifact": None,
            },
        ],
    }

    registry = build_capture_route_registry_from_board(board)
    routes = {item["route"]: item for item in registry["routes"]}

    assert routes["SelSaleReport"]["capture_route_name"] == "sales_documents_head"
    assert routes["SelSaleReport"]["capture_status"] == "ready_for_capture_admission"
    assert routes["SelSaleReport"]["capture_written_once"] is True
    assert routes["SelSaleReport"]["latest_capture_batch_id"] == "sales-batch-001"
    assert routes["SelSaleReport"]["route_kind"] == "head"
    assert routes["GetDIYReportData(E004001008_2)"]["capture_route_name"] == "sales_document_lines"
    assert routes["sales_reverse_document_lines"]["capture_status"] == "research_capture_only"
    assert routes["sales_reverse_document_lines"]["route_kind"] == "reverse"
    assert routes["库存明细统计 / SelDeptStockWaitList"]["capture_status"] == "ready_for_capture_admission"
    assert routes["库存明细统计 / SelDeptStockWaitList"]["capture_route_name"] == "inventory_stock_wait_lines"
    assert routes["库存明细统计 / SelDeptStockWaitList"]["capture_route_confirmed"] is True
    assert routes["库存明细统计 / SelDeptStockWaitList"]["route_kind"] == "stock"
    assert routes["库存明细统计 / SelDeptStockWaitList"]["capture_written_once"] is True
    assert routes["库存明细统计 / SelDeptStockWaitList"]["capture_parameter_plan"] == {
        "stockflag_values": ["0", "1"],
        "page_mode": "fixed_page_zero",
    }
    assert routes["会员中心 / SelVipInfoList"]["capture_status"] == "capture_candidate_blocked"
    assert routes["会员中心 / SelVipInfoList"]["capture_route_name"] == "member_profile_records"
    assert routes["会员中心 / SelVipInfoList"]["capture_written_once"] is True
    assert routes["会员中心 / SelVipInfoList"]["latest_capture_batch_id"] == "member-batch-001"
    assert routes["参数设置 / page_baseline"]["capture_status"] == "not_planned"
    assert routes["参数设置 / page_baseline"]["capture_route_name"] is None

    assert registry["summary"]["ready_for_capture_admission_count"] == 3
    assert registry["summary"]["captured_once_count"] == 5
    assert registry["summary"]["role_counts"]["exclude"] == 1


def test_render_capture_route_registry_markdown_includes_capture_sections() -> None:
    registry = {
        "summary": {
            "total_routes": 1,
            "usable_raw_route_count": 1,
            "confirmed_capture_route_count": 1,
            "ready_for_capture_admission_count": 1,
            "captured_once_count": 1,
            "global_gate_complete": True,
            "role_counts": {"mainline_fact": 1},
            "status_counts": {"ready_for_capture_admission": 1},
            "top_wave_blockers": {"wave_1_sales": {}},
        },
        "capture_principles": ["foo"],
        "routes": [
            {
                "route": "SelSaleReport",
                "source_kind": "主源候选",
                "capture_role_label": "主链事实",
                "capture_status_label": "可准入 capture",
                "capture_route_name": "sales_documents_head",
                "capture_route_confirmed": True,
                "route_kind": "head",
                "capture_written_once": True,
                "latest_capture_batch_id": "batch-001",
                "planned_capture_wave": "wave_1_sales",
                "menu_path": ["报表管理", "零售报表", "销售清单"],
                "blocking_issues": [],
                "next_action": "准备准入",
            }
        ],
    }

    markdown = render_capture_route_registry_markdown(registry)
    assert "# ERP Capture 路线注册表" in markdown
    assert "sales_documents_head" in markdown
    assert "可准入 capture" in markdown
