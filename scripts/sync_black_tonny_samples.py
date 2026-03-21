#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "data" / "sample"
FILES = [
    "manifest.json",
    "dashboard.json",
    "details.json",
    "monthly.json",
    "quarterly.json",
    "relationship.json",
]


def _default_source_candidates() -> list[Path]:
    return [
        ROOT.parent / "Black-Tonny" / "site" / "dashboard" / "data",
        ROOT.parent.parent / "Black-Tonny" / "site" / "dashboard" / "data",
    ]


def resolve_default_source() -> Path:
    candidates = _default_source_candidates()
    for candidate in candidates:
        if (candidate / "manifest.json").exists():
            return candidate
    return candidates[-1]


def sync_samples(source: Path) -> list[Path]:
    TARGET.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for name in FILES:
        src = source / name
        if not src.exists():
            raise FileNotFoundError(src)
        dst = TARGET / name
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync payload samples from the legacy Black-Tonny repository.")
    parser.add_argument("--source", type=Path, default=resolve_default_source())
    args = parser.parse_args()
    copied = sync_samples(args.source.resolve())
    print("Synced sample files:")
    for path in copied:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
