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

from app.services.yeusoft_page_research_service import load_page_research_manifests, summarize_page_manifests


LOCAL_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_RUN_ROOT = PROJECT_ROOT / "output" / "playwright" / "yeusoft-research"
DEFAULT_ANALYSIS_ROOT = PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"


def now_local() -> datetime:
    return datetime.now(LOCAL_TZ)


def main() -> int:
    parser = argparse.ArgumentParser(description="将 Playwright 页面研究原始 manifest 归纳成结构化分析结果。")
    parser.add_argument("--run-dir", help="某次 yeusoft-research 运行目录；默认取最新一次")
    parser.add_argument("--analysis-root", default=str(DEFAULT_ANALYSIS_ROOT), help="分析结果输出目录")
    args = parser.parse_args()

    if args.run_dir:
        run_dir = Path(args.run_dir)
    else:
        candidates = sorted(DEFAULT_RUN_ROOT.glob("*"))
        if not candidates:
            raise SystemExit("未找到任何 Playwright 页面研究运行目录")
        run_dir = candidates[-1]

    manifests = load_page_research_manifests(run_dir)
    summary = summarize_page_manifests(manifests)
    output_path = Path(args.analysis_root) / f"yeusoft-page-research-{run_dir.name}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({"ok": True, "run_dir": str(run_dir), "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
