from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DOCS = [
    "README.md",
    "ARCHITECTURE.md",
    "docs/README.md",
    "CONTRIBUTING.md",
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".claude/CLAUDE.md",
]
SKIP_DIRS = {".git", ".venv", ".playwright-cli", "output", "__pycache__"}
NUMERIC_PREFIX_ALLOWLIST: set[str] = set()
HAN_PATTERN = re.compile(r"[\u4e00-\u9fff]")
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]+)?\)")
ALLOWED_STATUSES = {
    "Source of truth",
    "Working doc",
    "Draft",
    "Reference",
}


def iter_markdown_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.md"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def repo_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def has_chinese(text: str) -> bool:
    return HAN_PATTERN.search(text) is not None


def is_external_link(target: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE))


def main() -> int:
    failures: list[str] = []
    markdown_files = iter_markdown_files(REPO_ROOT)

    for file_path in markdown_files:
        relative_path = repo_path(file_path)
        text = file_path.read_text(encoding="utf-8")

        if re.match(r"^\d{2}-", file_path.name) and relative_path not in NUMERIC_PREFIX_ALLOWLIST:
            failures.append(f"{relative_path}: numeric filename prefixes are not allowed")

        for match in MARKDOWN_LINK_PATTERN.finditer(text):
            target = match.group(1).strip()
            if not target or target.startswith("#") or is_external_link(target):
                continue
            resolved = (file_path.parent / target).resolve()
            if not resolved.exists():
                failures.append(f"{relative_path}: broken Markdown link target: {target}")

    for public_doc in PUBLIC_DOCS:
        path = REPO_ROOT / public_doc
        if not path.exists():
            failures.append(f"{public_doc}: required public doc is missing")
            continue
        if has_chinese(path.read_text(encoding="utf-8")):
            failures.append(
                f"{public_doc}: public-facing standard docs and AI entry docs must not contain Chinese characters"
            )

    docs_readme_path = REPO_ROOT / "docs" / "README.md"
    if docs_readme_path.exists():
        docs_readme_text = docs_readme_path.read_text(encoding="utf-8")
        if "## Status Legend" not in docs_readme_text:
            failures.append("docs/README.md: Status Legend section is required")
        statuses = re.findall(r"Status:\s*`([^`]+)`", docs_readme_text)
        for status in statuses:
            if status not in ALLOWED_STATUSES:
                failures.append(f"docs/README.md: invalid status value: {status}")

    for file_path in markdown_files:
        relative_path = repo_path(file_path)
        if not relative_path.startswith("docs/") or relative_path == "docs/README.md":
            continue
        if not has_chinese(file_path.read_text(encoding="utf-8")):
            failures.append(f"{relative_path}: internal working docs under docs/ must contain Chinese content")

    if failures:
        print("Documentation checks failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"Documentation checks passed for {len(markdown_files)} Markdown files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
