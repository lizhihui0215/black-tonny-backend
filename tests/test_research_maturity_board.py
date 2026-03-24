from __future__ import annotations

from app.services.research.maturity_board import resolve_page_research_record


def test_research_maturity_board_wrapper_supports_alias_resolution():
    records = {"会员消费排行榜": {"title": "会员消费排行榜", "status": "ok"}}

    resolved = resolve_page_research_record("会员消费排行", records)

    assert resolved is not None
    assert resolved["title"] == "会员消费排行榜"
