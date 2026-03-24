from __future__ import annotations

from app.services.capture.route_registry import (
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
                "mainline_ready": True,
                "blocking_issues": [],
                "next_action": "按默认空条件单请求写入 member_profile_records，并继续跟进 condition / VolumeNumber 的非阻塞语义。",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_parameter_plan": {
                    "default_condition": "",
                    "default_searchval": "",
                    "default_VolumeNumber": "",
                    "page_mode": "single_request_no_pagination",
                    "declared_total_count": 1309,
                    "full_capture_with_default_query": True,
                },
                "capture_written_once": True,
                "latest_capture_batch_id": "member-batch-001",
                "latest_capture_mode": "admission",
                "latest_capture_artifact": "tmp/capture-samples/analysis/member-capture-research-20260322-000262.json",
            },
            {
                "domain": "sales",
                "domain_label": "销售",
                "route": "客户资料 / SelDeptList",
                "title": "客户资料",
                "endpoint": "SelDeptList",
                "menu_path": ["基础资料", "客户资料"],
                "source_kind": "主源候选",
                "stage": "已HTTP回证",
                "reliability_status": "中等可信",
                "research_map_complete": True,
                "mainline_ready": True,
                "blocking_issues": [],
                "next_action": "已进入 capture admit；继续观察后续账号或页面上下文是否引入非空客户集合。",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_written_once": True,
                "latest_capture_batch_id": "customer-batch-001",
                "latest_capture_mode": "admission",
                "latest_capture_artifact": "tmp/capture-samples/analysis/customer-capture-admission-20260323-000000.json",
                "capture_admission_ready": True,
            },
            {
                "domain": "member",
                "domain_label": "会员",
                "route": "会员总和分析 / SelVipAnalysisReport",
                "title": "会员总和分析",
                "endpoint": "SelVipAnalysisReport",
                "menu_path": ["报表管理", "会员报表", "会员总和分析"],
                "source_kind": "结果快照",
                "stage": "已HTTP回证",
                "reliability_status": "中等可信",
                "research_map_complete": True,
                "mainline_ready": False,
                "blocking_issues": [],
                "next_action": "按 page=0 单请求写入 capture，并继续保持分析结果快照定位。",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_written_once": True,
                "latest_capture_batch_id": "member-analysis-snapshot-batch-001",
                "latest_capture_mode": "admission",
                "latest_capture_artifact": "tmp/capture-samples/analysis/member-analysis-snapshot-capture-admission-20260325-000321.json",
                "capture_admission_ready": True,
            },
            {
                "domain": "member",
                "domain_label": "会员",
                "route": "会员消费排行 / SelVipSaleRank",
                "title": "会员消费排行",
                "endpoint": "SelVipSaleRank",
                "menu_path": ["报表管理", "会员报表", "会员消费排行榜"],
                "source_kind": "结果快照",
                "stage": "已HTTP回证",
                "reliability_status": "中等可信",
                "research_map_complete": True,
                "mainline_ready": False,
                "blocking_issues": [],
                "next_action": "按 page=0 单请求写入 capture，并继续保持排行快照定位。",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_written_once": True,
                "latest_capture_batch_id": "member-sales-rank-snapshot-batch-001",
                "latest_capture_mode": "admission",
                "latest_capture_artifact": "tmp/capture-samples/analysis/member-sales-rank-snapshot-capture-admission-20260325-000221.json",
                "capture_admission_ready": True,
            },
            {
                "domain": "payment_and_docs",
                "domain_label": "流水单据",
                "route": "每日流水单 / SelectRetailDocPaymentSlip",
                "title": "每日流水单",
                "endpoint": "SelectRetailDocPaymentSlip",
                "menu_path": ["报表管理", "对账报表", "每日流水单"],
                "source_kind": "结果快照",
                "stage": "已HTTP回证",
                "reliability_status": "中等可信",
                "research_map_complete": True,
                "mainline_ready": False,
                "blocking_issues": [],
                "next_action": "按默认窗口单请求写入 capture，并继续保持结果快照定位。",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_written_once": True,
                "latest_capture_batch_id": "daily-payment-snapshot-batch-001",
                "latest_capture_mode": "admission",
                "latest_capture_artifact": "tmp/capture-samples/analysis/daily-payment-snapshot-capture-admission-20260325-000000.json",
                "capture_admission_ready": True,
            },
            {
                "domain": "payment_and_docs",
                "domain_label": "流水单据",
                "route": "收货确认 / SelDocConfirmList",
                "title": "收货确认",
                "endpoint": "SelDocConfirmList",
                "menu_path": ["单据管理", "上级往来", "收货确认"],
                "source_kind": "主源候选",
                "stage": "已HTTP回证",
                "reliability_status": "中等可信",
                "research_map_complete": True,
                "mainline_ready": True,
                "blocking_issues": [],
                "next_action": "收货确认主列表可先按空 payload 准入 capture；继续验证页面选中行和详情/确认动作链是否会补充隐藏参数或明细接口。",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_written_once": True,
                "latest_capture_batch_id": "receipt-batch-001",
                "latest_capture_mode": "admission",
                "latest_capture_artifact": "tmp/capture-samples/analysis/receipt-confirmation-capture-admission-20260323-000000.json",
                "capture_admission_ready": True,
            },
            {
                "domain": "payment_and_docs",
                "domain_label": "流水单据",
                "route": "门店盘点单 / SelDocManageList",
                "title": "门店盘点单",
                "endpoint": "SelDocManageList",
                "menu_path": ["单据管理", "盘点业务", "门店盘点单"],
                "source_kind": "主源候选",
                "stage": "已HTTP回证",
                "reliability_status": "中等可信",
                "research_map_complete": True,
                "mainline_ready": True,
                "blocking_issues": [],
                "next_action": "门店盘点单主列表可先按固定 stat/date 窗口准入 capture；继续确认查看明细、条码记录、统计损溢是否拆成独立二级接口。",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_written_once": True,
                "latest_capture_batch_id": "stocktaking-batch-001",
                "latest_capture_mode": "admission",
                "latest_capture_artifact": "tmp/capture-samples/analysis/store-stocktaking-capture-admission-20260323-000000.json",
                "capture_admission_ready": True,
            },
            {
                "domain": "payment_and_docs",
                "domain_label": "流水单据",
                "route": "门店盘点单 / store_stocktaking_diff_records",
                "title": "门店盘点单",
                "endpoint": "store_stocktaking_diff_records",
                "menu_path": ["单据管理", "盘点业务", "门店盘点单"],
                "source_kind": "研究留痕",
                "stage": "已单变量",
                "reliability_status": "中等可信",
                "research_map_complete": True,
                "mainline_ready": False,
                "blocking_issues": ["统计损溢当前更像本地派生数据"],
                "next_action": "继续验证本地损溢数据是否应固化为长期 secondary raw route。",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_written_once": True,
                "latest_capture_batch_id": "stocktaking-diff-batch-001",
                "latest_capture_mode": "research",
                "latest_capture_artifact": "tmp/capture-samples/analysis/store-stocktaking-diff-capture-research-20260324-000000.json",
            },
            {
                "domain": "sales",
                "domain_label": "销售",
                "route": "商品销售情况 / SelSaleReportData",
                "title": "商品销售情况",
                "endpoint": "SelSaleReportData",
                "menu_path": ["报表管理", "综合分析", "商品销售情况"],
                "source_kind": "结果快照",
                "stage": "已HTTP回证",
                "reliability_status": "中等可信",
                "research_map_complete": True,
                "mainline_ready": False,
                "blocking_issues": [],
                "next_action": "按默认时间窗单请求写入 capture，并继续保持结果快照定位。",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_written_once": True,
                "latest_capture_batch_id": "product-sales-snapshot-batch-001",
                "latest_capture_mode": "admission",
                "latest_capture_artifact": "tmp/capture-samples/analysis/product-sales-snapshot-capture-admission-20260325-000000.json",
                "capture_admission_ready": True,
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
    assert routes["会员中心 / SelVipInfoList"]["capture_status"] == "ready_for_capture_admission"
    assert routes["会员中心 / SelVipInfoList"]["capture_route_name"] == "member_profile_records"
    assert routes["会员中心 / SelVipInfoList"]["capture_written_once"] is True
    assert routes["会员中心 / SelVipInfoList"]["latest_capture_batch_id"] == "member-batch-001"
    assert routes["客户资料 / SelDeptList"]["capture_status"] == "ready_for_capture_admission"
    assert routes["客户资料 / SelDeptList"]["capture_route_name"] == "customer_master_records"
    assert routes["客户资料 / SelDeptList"]["capture_route_confirmed"] is True
    assert routes["客户资料 / SelDeptList"]["route_kind"] == "master"
    assert routes["商品销售情况 / SelSaleReportData"]["capture_role"] == "snapshot"
    assert routes["商品销售情况 / SelSaleReportData"]["capture_route_name"] == "product_sales_snapshot_records"
    assert routes["商品销售情况 / SelSaleReportData"]["capture_status"] == "snapshot_capture_optional"
    assert routes["会员总和分析 / SelVipAnalysisReport"]["capture_written_once"] is True
    assert routes["会员总和分析 / SelVipAnalysisReport"]["capture_route_name"] == "member_analysis_snapshot_records"
    assert routes["会员总和分析 / SelVipAnalysisReport"]["capture_status"] == "snapshot_capture_optional"
    assert routes["会员总和分析 / SelVipAnalysisReport"]["capture_route_confirmed"] is True
    assert routes["会员总和分析 / SelVipAnalysisReport"]["route_kind"] == "snapshot"
    assert routes["会员消费排行 / SelVipSaleRank"]["capture_written_once"] is True
    assert routes["会员消费排行 / SelVipSaleRank"]["capture_route_name"] == "member_sales_rank_snapshot_records"
    assert routes["会员消费排行 / SelVipSaleRank"]["capture_status"] == "snapshot_capture_optional"
    assert routes["会员消费排行 / SelVipSaleRank"]["capture_route_confirmed"] is True
    assert routes["会员消费排行 / SelVipSaleRank"]["route_kind"] == "snapshot"
    assert routes["每日流水单 / SelectRetailDocPaymentSlip"]["capture_written_once"] is True
    assert routes["每日流水单 / SelectRetailDocPaymentSlip"]["capture_route_name"] == "daily_payment_slips_snapshot"
    assert routes["每日流水单 / SelectRetailDocPaymentSlip"]["capture_status"] == "snapshot_capture_optional"
    assert routes["每日流水单 / SelectRetailDocPaymentSlip"]["capture_route_confirmed"] is True
    assert routes["每日流水单 / SelectRetailDocPaymentSlip"]["route_kind"] == "snapshot"
    assert routes["收货确认 / SelDocConfirmList"]["capture_route_name"] == "receipt_confirmation_documents"
    assert routes["收货确认 / SelDocConfirmList"]["capture_status"] == "ready_for_capture_admission"
    assert routes["收货确认 / SelDocConfirmList"]["capture_written_once"] is True
    assert routes["收货确认 / SelDocConfirmList"]["latest_capture_batch_id"] == "receipt-batch-001"
    assert routes["收货确认 / SelDocConfirmList"]["capture_route_confirmed"] is True
    assert routes["收货确认 / SelDocConfirmList"]["route_kind"] == "document"
    assert routes["门店盘点单 / SelDocManageList"]["capture_route_name"] == "store_stocktaking_documents"
    assert routes["门店盘点单 / SelDocManageList"]["capture_status"] == "ready_for_capture_admission"
    assert routes["门店盘点单 / SelDocManageList"]["capture_written_once"] is True
    assert routes["门店盘点单 / SelDocManageList"]["latest_capture_batch_id"] == "stocktaking-batch-001"
    assert routes["门店盘点单 / SelDocManageList"]["capture_route_confirmed"] is True
    assert routes["门店盘点单 / SelDocManageList"]["route_kind"] == "document"
    assert routes["门店盘点单 / store_stocktaking_diff_records"]["capture_status"] == "research_capture_only"
    assert routes["门店盘点单 / store_stocktaking_diff_records"]["capture_route_name"] == "store_stocktaking_diff_records"
    assert routes["门店盘点单 / store_stocktaking_diff_records"]["capture_route_confirmed"] is True
    assert routes["门店盘点单 / store_stocktaking_diff_records"]["route_kind"] == "diff"
    assert routes["参数设置 / page_baseline"]["capture_status"] == "not_planned"
    assert routes["参数设置 / page_baseline"]["capture_route_name"] is None
    assert registry["summary"]["blocked_mainline_candidate_count"] == 0
    assert registry["summary"]["blocked_mainline_candidates"] == []


def test_build_capture_route_registry_uses_member_maintenance_override() -> None:
    board = {
        "summary": {"global_risk_map_complete": True},
        "entries": [
            {
                "domain": "member",
                "domain_label": "会员",
                "route": "会员维护 / SelVipReturnVisitList",
                "title": "会员维护",
                "endpoint": "YisEposVipReturnVisit/SelVipReturnVisitList",
                "menu_path": ["会员资料", "会员维护"],
                "source_kind": "主源候选",
                "stage": "已HTTP回证",
                "reliability_status": "能跑但不能信",
                "research_map_complete": True,
                "mainline_ready": False,
                "blocking_issues": ["当前账号 baseline 为空数据集，且接口返回 errcode=1000"],
                "next_action": "先确认当前账号是否真实无会员回访数据，或页面动作链是否会补充隐藏上下文，再评估 capture 准入。",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_written_once": False,
                "latest_capture_batch_id": None,
                "latest_capture_mode": None,
                "latest_capture_artifact": None,
            }
        ],
    }

    registry = build_capture_route_registry_from_board(board)
    route = registry["routes"][0]

    assert route["capture_route_name"] == "member_maintenance_records"


def test_build_capture_route_registry_uses_stored_value_detail_override() -> None:
    board = {
        "summary": {"global_risk_map_complete": True},
        "entries": [
            {
                "domain": "stored_value",
                "domain_label": "储值",
                "route": "储值卡明细 / GetDIYReportData",
                "title": "储值卡明细",
                "endpoint": "GetDIYReportData",
                "menu_path": ["报表管理", "会员报表", "储值卡明细"],
                "source_kind": "主源候选",
                "stage": "已HTTP回证",
                "reliability_status": "中等可信",
                "research_map_complete": True,
                "mainline_ready": True,
                "blocking_issues": [],
                "next_action": "按默认空 Search 单请求准入 capture。",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_parameter_plan": {
                    "default_Search": "",
                    "search_mode": "vip_card_only_filter",
                    "page_mode": "single_request_half_open_date_verified",
                },
                "capture_written_once": True,
                "latest_capture_batch_id": "stored-value-admit-001",
                "latest_capture_mode": "admission",
                "latest_capture_artifact": "tmp/capture-samples/analysis/stored-value-capture-admission-20260323-000122.json",
            }
        ],
    }

    registry = build_capture_route_registry_from_board(board)
    route = registry["routes"][0]

    assert route["capture_route_name"] == "stored_value_card_detail"
    assert route["capture_route_confirmed"] is True
    assert route["route_kind"] == "detail"
    assert route["capture_status"] == "ready_for_capture_admission"


def test_build_capture_route_registry_uses_stored_value_override() -> None:
    board = {
        "summary": {"global_risk_map_complete": True},
        "entries": [
            {
                "domain": "stored_value",
                "domain_label": "储值",
                "route": "储值卡明细 / GetDIYReportData",
                "title": "储值卡明细",
                "endpoint": "FXDIYReport/GetDIYReportData",
                "menu_path": ["报表管理", "会员报表", "储值卡明细"],
                "source_kind": "主源候选",
                "stage": "已HTTP回证",
                "reliability_status": "中等可信",
                "research_map_complete": True,
                "mainline_ready": False,
                "blocking_issues": ["尚未确认是否存在隐藏分页或服务端上限"],
                "next_action": "先按默认空 Search 留痕进入 capture research，并继续确认 Search 语义与隐藏分页上限。",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_written_once": True,
                "latest_capture_batch_id": "stored-value-batch-001",
                "latest_capture_mode": "research",
                "latest_capture_artifact": "tmp/capture-samples/analysis/stored-value-capture-research-20260323-000121.json",
            }
        ],
    }

    registry = build_capture_route_registry_from_board(board)
    route = registry["routes"][0]

    assert route["capture_route_name"] == "stored_value_card_detail"
    assert route["capture_status"] == "capture_candidate_blocked"
    assert route["planned_capture_wave"] == "wave_3_stored_value"
    assert route["capture_written_once"] is True
    assert route["latest_capture_batch_id"] == "stored-value-batch-001"
    assert route["capture_route_confirmed"] is True
    assert route["route_kind"] == "detail"


def test_build_capture_route_registry_uses_stored_value_card_summary_snapshot_override() -> None:
    board = {
        "summary": {"global_risk_map_complete": True},
        "entries": [
            {
                "domain": "stored_value",
                "domain_label": "储值",
                "route": "储值卡汇总 / GetDIYReportData",
                "title": "储值卡汇总",
                "endpoint": "FXDIYReport/GetDIYReportData",
                "menu_path": ["报表管理", "会员报表", "储值卡汇总"],
                "source_kind": "结果快照",
                "stage": "已HTTP回证",
                "reliability_status": "中等可信",
                "research_map_complete": True,
                "mainline_ready": False,
                "blocking_issues": [],
                "next_action": "按默认 Search 空值单请求写入 capture。",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_written_once": True,
                "latest_capture_batch_id": "stored-value-card-summary-batch-001",
                "latest_capture_mode": "admission",
                "latest_capture_artifact": "tmp/capture-samples/analysis/stored-value-card-summary-snapshot-capture-admission-20260325-000001.json",
            }
        ],
    }

    registry = build_capture_route_registry_from_board(board)
    route = registry["routes"][0]

    assert route["capture_route_name"] == "stored_value_card_summary_snapshot_records"
    assert route["capture_status"] == "snapshot_capture_optional"
    assert route["capture_route_confirmed"] is True
    assert route["route_kind"] == "snapshot"


def test_build_capture_route_registry_uses_stored_value_by_store_snapshot_override() -> None:
    board = {
        "summary": {"global_risk_map_complete": True},
        "entries": [
            {
                "domain": "stored_value",
                "domain_label": "储值",
                "route": "储值按店汇总 / GetDIYReportData",
                "title": "储值按店汇总",
                "endpoint": "FXDIYReport/GetDIYReportData",
                "menu_path": ["报表管理", "会员报表", "储值按店汇总"],
                "source_kind": "结果快照",
                "stage": "已HTTP回证",
                "reliability_status": "中等可信",
                "research_map_complete": True,
                "mainline_ready": False,
                "blocking_issues": [],
                "next_action": "按默认时间窗单请求写入 capture。",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_written_once": True,
                "latest_capture_batch_id": "stored-value-by-store-batch-001",
                "latest_capture_mode": "admission",
                "latest_capture_artifact": "tmp/capture-samples/analysis/stored-value-by-store-snapshot-capture-admission-20260325-000001.json",
            }
        ],
    }

    registry = build_capture_route_registry_from_board(board)
    route = registry["routes"][0]

    assert route["capture_route_name"] == "stored_value_by_store_snapshot_records"
    assert route["capture_status"] == "snapshot_capture_optional"
    assert route["capture_route_confirmed"] is True
    assert route["route_kind"] == "snapshot"


def test_render_capture_route_registry_markdown_includes_capture_sections() -> None:
    registry = {
        "summary": {
            "total_routes": 1,
            "usable_raw_route_count": 1,
            "confirmed_capture_route_count": 1,
            "ready_for_capture_admission_count": 1,
            "captured_once_count": 1,
            "blocked_mainline_candidate_count": 0,
            "blocked_mainline_candidates": [],
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


def test_build_capture_route_registry_surfaces_blocked_mainline_candidates() -> None:
    board = {
        "summary": {"global_risk_map_complete": True},
        "entries": [
            {
                "domain": "payment_and_docs",
                "domain_label": "流水单据",
                "route": "退货明细 / SelReturnStockList",
                "title": "退货明细",
                "endpoint": "SelReturnStockList",
                "menu_path": ["报表管理", "进出报表", "退货明细"],
                "source_kind": "主源候选",
                "stage": "已HTTP回证",
                "reliability_status": "能跑但不能信",
                "research_map_complete": True,
                "mainline_ready": False,
                "blocking_issues": ["当前 seed type 值全部触发服务端错误"],
                "next_action": "继续定位隐藏上下文或服务端边界。",
                "ingestion_blocked_by_global_gate": False,
                "analysis_sources": [],
                "capture_written_once": True,
                "latest_capture_batch_id": "return-batch-001",
                "latest_capture_mode": "research",
                "latest_capture_artifact": "tmp/capture-samples/analysis/return-detail-capture-research-20260324-230648.json",
            }
        ],
    }

    registry = build_capture_route_registry_from_board(board)

    assert registry["summary"]["blocked_mainline_candidate_count"] == 1
    assert registry["summary"]["blocked_mainline_candidates"] == ["退货明细 / SelReturnStockList"]
