from __future__ import annotations

import json
from pathlib import Path

from scripts.probe_yeusoft_store_stocktaking_ui_actions import _resolve_page_entry


def test_resolve_store_stocktaking_entry_from_menu_coverage(tmp_path: Path) -> None:
    report_doc = tmp_path / "report_api_samples.md"
    report_doc.write_text("", "utf-8")
    api_images_dir = tmp_path / "API-images"
    api_images_dir.mkdir()

    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir()
    (analysis_root / "menu-coverage-audit-20260323-000002.json").write_text(
        json.dumps(
            {
                "pages": [
                    {
                        "title": "门店盘点单",
                        "root_name": "单据管理",
                        "group_name": "盘点业务",
                        "menu_path": ["单据管理", "盘点业务", "门店盘点单"],
                        "coverage_status": "covered",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        "utf-8",
    )

    entry = _resolve_page_entry(
        "门店盘点单",
        analysis_root,
        report_doc=report_doc,
        api_images_dir=api_images_dir,
    )

    assert entry.title == "门店盘点单"
    assert entry.menu_root_name == "单据管理"
    assert entry.target_menu_path == ("单据管理", "盘点业务", "门店盘点单")
