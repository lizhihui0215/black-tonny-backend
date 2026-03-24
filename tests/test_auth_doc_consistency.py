from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_repo_file(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_runtime_auth_docs_match_current_backend_boundary() -> None:
    architecture_doc = _read_repo_file("ARCHITECTURE.md")
    frontend_auth_doc = _read_repo_file("docs/frontend-auth-api.md")
    assistant_doc = _read_repo_file("docs/assistant/chat-api.md")
    dashboard_doc = _read_repo_file("docs/dashboard/summary-api.md")

    assert "do not require a frontend bearer token" in architecture_doc
    assert "不依赖 frontend bearer token" in frontend_auth_doc
    assert "当前 runtime phase 不要求 frontend bearer access token" in assistant_doc
    assert "当前 runtime phase 不要求 frontend bearer access token" in dashboard_doc


def test_runtime_auth_docs_match_current_route_sources() -> None:
    assistant_route_source = _read_repo_file("app/api/routes/assistant.py")
    dashboard_route_source = _read_repo_file("app/api/routes/dashboard.py")

    assert "require_frontend_user" not in assistant_route_source
    assert "require_frontend_user" not in dashboard_route_source
