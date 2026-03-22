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

from app.services.capture_route_registry_service import (  # noqa: E402
    build_capture_route_registry,
    render_capture_route_registry_markdown,
)

LOCAL_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_ANALYSIS_ROOT = PROJECT_ROOT / "tmp" / "capture-samples" / "analysis"
DEFAULT_REGISTRY_DOC = PROJECT_ROOT / "docs" / "erp" / "capture-route-registry.md"


def now_local() -> datetime:
    return datetime.now(LOCAL_TZ)


def main() -> int:
    parser = argparse.ArgumentParser(description="从 ERP API 成熟度状态板生成 capture 路线注册表。")
    parser.add_argument("--analysis-root", default=str(DEFAULT_ANALYSIS_ROOT), help="analysis 目录")
    parser.add_argument("--registry-doc", default=str(DEFAULT_REGISTRY_DOC), help="输出 Markdown 注册表路径")
    parser.add_argument("--registry-json", help="输出 JSON 路径；默认写入 analysis/capture-route-registry-<timestamp>.json")
    args = parser.parse_args()

    analysis_root = Path(args.analysis_root)
    registry_doc = Path(args.registry_doc)
    registry_json = (
        Path(args.registry_json)
        if args.registry_json
        else analysis_root / f"capture-route-registry-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    )

    registry = build_capture_route_registry(PROJECT_ROOT, analysis_root)
    markdown = render_capture_route_registry_markdown(registry)

    registry_doc.parent.mkdir(parents=True, exist_ok=True)
    registry_doc.write_text(markdown, "utf-8")
    registry_json.parent.mkdir(parents=True, exist_ok=True)
    registry_json.write_text(json.dumps(registry, ensure_ascii=False, indent=2), "utf-8")

    print(f"Markdown registry written to {registry_doc}")
    print(f"JSON registry written to {registry_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
