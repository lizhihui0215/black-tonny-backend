from __future__ import annotations

import json
from pathlib import Path

from scripts.probe_yeusoft_return_detail_ui_filters import _resolve_page_entry


def test_resolve_page_entry_falls_back_to_menu_coverage_audit(tmp_path: Path) -> None:
    report_doc = tmp_path / "report_api_samples.md"
    report_doc.write_text("", "utf-8")
    api_images_dir = tmp_path / "API-images"
    api_images_dir.mkdir()

    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir()
    (analysis_root / "menu-coverage-audit-20260323-000000.json").write_text(
        json.dumps(
            {
                "pages": [
                    {
                        "title": "退货明细",
                        "root_name": "报表管理",
                        "group_name": "进出报表",
                        "menu_path": ["报表管理", "进出报表", "退货明细"],
                        "coverage_status": "covered",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        "utf-8",
    )

    entry = _resolve_page_entry(
        "退货明细",
        analysis_root,
        report_doc=report_doc,
        api_images_dir=api_images_dir,
    )

    assert entry.title == "退货明细"
    assert entry.menu_root_name == "报表管理"
    assert entry.target_menu_path == ("报表管理", "进出报表", "退货明细")
