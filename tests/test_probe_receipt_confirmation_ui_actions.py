from __future__ import annotations

import json
from pathlib import Path

from scripts.probe_yeusoft_receipt_confirmation_ui_actions import _resolve_page_entry


def test_resolve_receipt_confirmation_entry_from_menu_coverage(tmp_path: Path) -> None:
    report_doc = tmp_path / "report_api_samples.md"
    report_doc.write_text("", "utf-8")
    api_images_dir = tmp_path / "API-images"
    api_images_dir.mkdir()

    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir()
    (analysis_root / "menu-coverage-audit-20260323-000001.json").write_text(
        json.dumps(
            {
                "pages": [
                    {
                        "title": "收货确认",
                        "root_name": "单据管理",
                        "group_name": "上级往来",
                        "menu_path": ["单据管理", "上级往来", "收货确认"],
                        "coverage_status": "covered",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        "utf-8",
    )

    entry = _resolve_page_entry(
        "收货确认",
        analysis_root,
        report_doc=report_doc,
        api_images_dir=api_images_dir,
    )

    assert entry.title == "收货确认"
    assert entry.menu_root_name == "单据管理"
    assert entry.target_menu_path == ("单据管理", "上级往来", "收货确认")
