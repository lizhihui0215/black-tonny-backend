#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.research.maturity_board import (  # noqa: E402
    build_api_maturity_board,
    render_api_maturity_board_markdown,
)

LOCAL_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_ANALYSIS_ROOT = PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"
DEFAULT_BOARD_DOC = PROJECT_ROOT / "docs" / "erp" / "api-maturity-board.md"


def now_local() -> datetime:
    return datetime.now(LOCAL_TZ)


def main() -> int:
    parser = argparse.ArgumentParser(description="从现有 ERP 研究产物生成统一的 API 成熟度状态板。")
    parser.add_argument("--analysis-root", default=str(DEFAULT_ANALYSIS_ROOT), help="analysis 目录")
    parser.add_argument("--board-doc", default=str(DEFAULT_BOARD_DOC), help="输出 Markdown 状态板路径")
    parser.add_argument("--board-json", help="输出 JSON 路径；默认写入 analysis/api-maturity-board-<timestamp>.json")
    args = parser.parse_args()

    analysis_root = Path(args.analysis_root)
    board_doc = Path(args.board_doc)
    board_json = (
        Path(args.board_json)
        if args.board_json
        else analysis_root / f"api-maturity-board-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    )

    board = build_api_maturity_board(PROJECT_ROOT, analysis_root)
    markdown = render_api_maturity_board_markdown(board)

    board_doc.parent.mkdir(parents=True, exist_ok=True)
    board_doc.write_text(markdown, "utf-8")
    board_json.parent.mkdir(parents=True, exist_ok=True)
    board_json.write_text(json.dumps(board, ensure_ascii=False, indent=2), "utf-8")

    print(f"Markdown board written to {board_doc}")
    print(f"JSON board written to {board_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
