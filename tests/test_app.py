from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import clear_settings_cache
from app.db.engine import clear_engine_cache


def _configure_test_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APP_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'app.db'}")
    monkeypatch.setenv("PAYLOAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "sample"))
    monkeypatch.setenv("ADMIN_API_TOKEN", "test-token")
    clear_settings_cache()
    clear_engine_cache()


def test_health_and_manifest(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.main import app

    with TestClient(app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert "API 服务" in root.text
        assert "MySQL" in root.text
        assert "/api/status" in root.text
        assert "/api/manifest" in root.text
        assert "/redoc" in root.text
        health = client.get("/api/health")
        assert health.status_code == 200
        status = client.get("/api/status")
        assert status.status_code == 200
        status_payload = status.json()
        assert "runtime" in status_payload
        assert "components" in status_payload
        assert "system" in status_payload
        assert "cache_summary" in status_payload
        assert "database_summary" in status_payload
        assert status_payload["runtime"]["hostname"]
        assert status_payload["runtime"]["python_version"]
        assert status_payload["runtime"]["process_id"] > 0
        assert "disk_total_bytes" in status_payload["system"]
        assert "disk_used_bytes" in status_payload["system"]
        assert "disk_free_bytes" in status_payload["system"]
        assert "load_avg" in status_payload["system"]
        assert "table_counts" in status_payload["database_summary"]
        assert status_payload["components"]["analysis_source"]["status"] == "warning"
        manifest = client.get("/api/manifest")
        assert manifest.status_code == 200
        payload = manifest.json()
        assert payload["available_pages"]["dashboard"] == "/api/pages/dashboard"


def test_rebuild_job_refreshes_cache(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.main import app

    with TestClient(app) as client:
        response = client.post(
            "/api/jobs/rebuild",
            headers={"X-Admin-Token": "test-token"},
            json={"sync_mode": "full", "build_only": False},
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        detail = client.get(f"/api/jobs/{job_id}")
        assert detail.status_code == 200
        assert detail.json()["status"] in {"queued", "running", "success"}
