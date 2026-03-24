from __future__ import annotations

from app.services.research.menu_coverage import (
    build_menu_coverage_audit,
    infer_domain_from_menu_metadata,
)
from app.services.research.page_research import ResearchPageRecipe, ResearchPageRegistryEntry


def _entry(
    *,
    title: str,
    menu_root_name: str,
    group_name: str,
    menu_target_title: str | None = None,
) -> ResearchPageRegistryEntry:
    target_title = menu_target_title or title
    return ResearchPageRegistryEntry(
        title=title,
        canonical_name=title,
        slug=title,
        menu_target_title=target_title,
        menu_root_name=menu_root_name,
        group_name=group_name,
        menu_path=tuple(part for part in (menu_root_name, group_name, title) if part),
        target_menu_path=tuple(part for part in (menu_root_name, group_name, target_title) if part),
        sample_url=None,
        sample_payload=None,
        image_evidence_count=0,
        variant_label=None,
        variant_of=None,
        recipe=ResearchPageRecipe(),
    )


def test_infer_domain_from_menu_metadata_handles_known_groups():
    assert infer_domain_from_menu_metadata("报表管理", "零售报表", "销售清单") == ("sales", "销售")
    assert infer_domain_from_menu_metadata("报表管理", "库存报表", "库存明细统计") == ("inventory", "库存")
    assert infer_domain_from_menu_metadata("会员资料", "", "会员中心") == ("member", "会员")
    assert infer_domain_from_menu_metadata("其他", "", "VIP卡折扣管理") == ("member", "会员")
    assert infer_domain_from_menu_metadata("报表管理", "对账报表", "每日流水单") == ("payment_and_docs", "流水单据")


def test_build_menu_coverage_audit_classifies_covered_unknown_failed_and_containers():
    menu_list = [
        {
            "FuncName": "报表管理",
            "SubList": [
                {
                    "FuncName": "零售报表",
                    "SubList": [
                        {"FuncName": "销售清单", "FuncUrl": "sales"},
                        {"FuncName": "零售明细统计", "FuncUrl": "retail"},
                    ],
                },
                {
                    "FuncName": "库存报表",
                    "SubList": [
                        {"FuncName": "库存综合分析", "FuncUrl": "stock-analysis"},
                    ],
                },
            ],
        },
        {
            "FuncName": "会员资料",
            "SubList": [
                {"FuncName": "会员中心", "FuncUrl": "member-center"},
            ],
        },
    ]
    registry = [
        _entry(title="销售清单", menu_root_name="报表管理", group_name="零售报表"),
        _entry(title="库存综合分析-按中分类", menu_root_name="报表管理", group_name="库存报表", menu_target_title="库存综合分析"),
        _entry(title="会员中心", menu_root_name="会员资料", group_name=""),
    ]
    audited_pages = [
        {
            "title": "销售清单",
            "menu_path": ["报表管理", "零售报表", "销售清单"],
            "open_status": "opened",
            "candidate_endpoints": ["SelSaleReport"],
            "candidate_data_endpoints": ["SelSaleReport"],
            "visible_control_count": 12,
        },
        {
            "title": "零售明细统计",
            "menu_path": ["报表管理", "零售报表", "零售明细统计"],
            "open_status": "opened",
            "candidate_endpoints": ["SelDeptSaleList"],
            "candidate_data_endpoints": ["SelDeptSaleList"],
            "visible_control_count": 8,
        },
        {
            "title": "库存综合分析",
            "menu_path": ["报表管理", "库存报表", "库存综合分析"],
            "open_status": "failed",
            "error": "missing variant button",
            "candidate_endpoints": [],
            "candidate_data_endpoints": [],
            "visible_control_count": 4,
        },
        {
            "title": "会员中心",
            "menu_path": ["会员资料", "会员中心"],
            "open_status": "opened",
            "candidate_endpoints": ["SelVipInfoList"],
            "candidate_data_endpoints": ["SelVipInfoList"],
            "visible_control_count": 10,
        },
    ]
    latest_page_research = [
        {
            "title": "库存综合分析-按中分类",
            "endpoint_summaries": [
                {"endpoint": "SelStockAnalysisList", "is_data_endpoint": True},
            ],
        }
    ]

    audit = build_menu_coverage_audit(
        menu_list=menu_list,
        registry=registry,
        audited_pages=audited_pages,
        latest_page_research_pages=latest_page_research,
    )

    pages = {tuple(item["menu_path"]): item for item in audit["pages"]}
    assert audit["summary"]["clickable_page_count"] == 4
    assert audit["summary"]["covered_count"] == 2
    assert audit["summary"]["visible_but_untracked_count"] == 1
    assert audit["summary"]["visible_but_failed_count"] == 1
    assert audit["summary"]["audit_complete"] is True
    assert audit["summary"]["all_visible_pages_classified"] is True
    assert audit["containers"][0]["coverage_status"] == "container_only"

    assert pages[("报表管理", "零售报表", "销售清单")]["coverage_status"] == "covered"
    assert pages[("报表管理", "零售报表", "零售明细统计")]["coverage_status"] == "visible_but_untracked"
    assert pages[("报表管理", "库存报表", "库存综合分析")]["coverage_status"] == "visible_but_failed"
    assert pages[("报表管理", "库存报表", "库存综合分析")]["candidate_endpoints"] == ["SelStockAnalysisList"]
    assert pages[("会员资料", "会员中心")]["coverage_status"] == "covered"

    unknown = audit["summary"]["unknown_pages"][0]
    assert unknown["title"] == "零售明细统计"


def test_build_menu_coverage_audit_marks_unknown_page_as_covered_when_raw_manifest_exists():
    menu_list = [
        {
            "FuncName": "基础资料",
            "SubList": [
                {"FuncName": "商品资料", "FuncUrl": "WareInfo"},
            ],
        }
    ]
    audited_pages = [
        {
            "title": "商品资料",
            "menu_path": ["基础资料", "商品资料"],
            "open_status": "opened",
            "candidate_endpoints": [],
            "candidate_data_endpoints": [],
            "visible_control_count": 6,
        }
    ]
    latest_page_research = [
        {
            "page": {
                "title": "商品资料",
                "target_menu_path": ["基础资料", "商品资料"],
            },
            "network": {
                "requests": [],
                "responses": [],
            },
        }
    ]

    audit = build_menu_coverage_audit(
        menu_list=menu_list,
        registry=[],
        audited_pages=audited_pages,
        latest_page_research_pages=latest_page_research,
    )

    page = audit["pages"][0]
    assert page["coverage_status"] == "covered"
    assert page["matched_page_research_titles"] == ["商品资料"]
    assert audit["summary"]["visible_but_untracked_count"] == 0
