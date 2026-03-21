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

from app.services.erp_research_service import build_report_matrix

DEFAULT_REPORT_DOC = PROJECT_ROOT / "tmp" / "capture-samples" / "report_api_samples.md"
DEFAULT_RAW_ROOT = PROJECT_ROOT / "tmp" / "capture-samples" / "raw"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"
LOCAL_TZ = ZoneInfo("Asia/Shanghai")


def main() -> int:
    parser = argparse.ArgumentParser(description="分析已知 Yeusoft 报表样本的过滤条件、分页和字段可见性风险。")
    parser.add_argument("--report-doc", default=str(DEFAULT_REPORT_DOC), help="report_api_samples.md 路径")
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT), help="raw 样本目录")
    parser.add_argument("--output", help="输出 JSON 文件路径；默认写入 tmp/capture-samples/analysis")
    args = parser.parse_args()

    report_doc_path = Path(args.report_doc)
    raw_root = Path(args.raw_root)
    output_path = (
        Path(args.output)
        if args.output
        else DEFAULT_OUTPUT_ROOT / f"report-matrix-{datetime.now(LOCAL_TZ).strftime('%Y%m%d-%H%M%S')}.json"
    )

    matrix = build_report_matrix(report_doc_path, raw_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(matrix, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({"ok": True, "report_count": len(matrix), "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
