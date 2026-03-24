from __future__ import annotations

from app.services.research.menu_coverage import (
    build_menu_coverage_audit,
    load_latest_menu_coverage_audit,
)
from app.services.research.page_research import (
    ResearchPageRegistryEntry,
    build_page_research_registry,
    list_menu_items,
    load_page_research_manifests,
)


def test_research_page_wrappers_are_importable():
    assert ResearchPageRegistryEntry is not None
    assert callable(build_page_research_registry)
    assert callable(load_page_research_manifests)
    assert callable(list_menu_items)
    assert callable(build_menu_coverage_audit)
    assert callable(load_latest_menu_coverage_audit)
