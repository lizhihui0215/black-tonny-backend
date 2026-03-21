from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from sqlalchemy import delete, insert, select

from app.core.config import get_settings
from app.core.timezone import now_iso, now_local
from app.db.base import payload_cache_index
from app.db.engine import get_app_engine
from app.schemas.manifest import ManifestResponse


PAGE_KEYS = ("dashboard", "details", "monthly", "quarterly", "relationship")


def ensure_payload_directories() -> None:
    settings = get_settings()
    settings.payload_cache_path.mkdir(parents=True, exist_ok=True)
    settings.sample_data_path.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _manifest_path(base_dir: Path) -> Path:
    return base_dir / "manifest.json"


def _page_path(base_dir: Path, page_key: str) -> Path:
    return base_dir / f"{page_key}.json"


def _resolve_manifest_source() -> Path:
    settings = get_settings()
    cache_manifest = _manifest_path(settings.payload_cache_path)
    if cache_manifest.exists():
        return settings.payload_cache_path
    return settings.sample_data_path


def load_raw_manifest() -> dict[str, Any]:
    source_dir = _resolve_manifest_source()
    return _load_json(_manifest_path(source_dir))


def build_api_manifest(raw_manifest: dict[str, Any]) -> ManifestResponse:
    available_pages = {
        page_key: f"/api/pages/{page_key}"
        for page_key in PAGE_KEYS
        if page_key in (raw_manifest.get("available_pages") or {})
    }
    return ManifestResponse(
        generated_at=raw_manifest.get("generated_at"),
        date_tag=raw_manifest.get("date_tag"),
        store_name=raw_manifest.get("store_name"),
        analysis_batch_id=raw_manifest.get("analysis_batch_id"),
        available_pages=available_pages,
        available_exports=raw_manifest.get("available_exports") or {},
        pipeline=raw_manifest.get("pipeline") or [],
    )


def get_manifest() -> ManifestResponse:
    return build_api_manifest(load_raw_manifest())


def get_page_payload(page_key: str) -> dict[str, Any]:
    if page_key not in PAGE_KEYS:
        raise KeyError(page_key)
    source_dir = _resolve_manifest_source()
    page_path = _page_path(source_dir, page_key)
    if not page_path.exists():
        raise FileNotFoundError(page_path)
    return _load_json(page_path)


def get_payload_cache_summary() -> dict[str, Any]:
    settings = get_settings()
    source_dir = _resolve_manifest_source()
    source_mode = "cache" if source_dir == settings.payload_cache_path else "sample"
    manifest_path = _manifest_path(source_dir)
    manifest_exists = manifest_path.exists()
    manifest = _load_json(manifest_path) if manifest_exists else {}
    page_count = sum(1 for page_key in PAGE_KEYS if _page_path(source_dir, page_key).exists())
    cache_page_count = sum(1 for page_key in PAGE_KEYS if _page_path(settings.payload_cache_path, page_key).exists())
    cache_rows: list[dict[str, Any]] = []
    try:
        engine = get_app_engine()
        with engine.begin() as connection:
            cache_rows = connection.execute(select(payload_cache_index)).mappings().all()
    except Exception:
        cache_rows = []

    latest_cache_update = None
    if cache_rows:
        latest = max((row.get("updated_at") for row in cache_rows if row.get("updated_at")), default=None)
        if latest is not None:
            latest_cache_update = latest.isoformat()

    return {
        "source_mode": source_mode,
        "manifest_exists": manifest_exists,
        "page_count": page_count,
        "expected_page_count": len(PAGE_KEYS),
        "cache_page_count": cache_page_count,
        "cache_index_count": len(cache_rows),
        "cache_updated_at": latest_cache_update,
        "store_name": manifest.get("store_name"),
        "analysis_batch_id": manifest.get("analysis_batch_id"),
        "generated_at": manifest.get("generated_at"),
    }


def _update_cache_index(manifest: dict[str, Any]) -> None:
    now = now_local()
    settings = get_settings()
    engine = get_app_engine()
    with engine.begin() as connection:
        connection.execute(delete(payload_cache_index))
        for page_key in PAGE_KEYS:
            page_path = _page_path(settings.payload_cache_path, page_key)
            if not page_path.exists():
                continue
            try:
                relative_path = str(page_path.relative_to(settings.project_root))
            except ValueError:
                relative_path = str(page_path)
            connection.execute(
                insert(payload_cache_index).values(
                    page_key=page_key,
                    relative_path=relative_path,
                    generated_at=str(manifest.get("generated_at") or ""),
                    analysis_batch_id=str(manifest.get("analysis_batch_id") or ""),
                    store_name=str(manifest.get("store_name") or ""),
                    updated_at=now,
                )
            )


def refresh_cache_from_sample() -> ManifestResponse:
    settings = get_settings()
    ensure_payload_directories()
    source_manifest = _manifest_path(settings.sample_data_path)
    if not source_manifest.exists():
        raise FileNotFoundError(source_manifest)
    shutil.copy2(source_manifest, _manifest_path(settings.payload_cache_path))
    for page_key in PAGE_KEYS:
        source_page = _page_path(settings.sample_data_path, page_key)
        if source_page.exists():
            shutil.copy2(source_page, _page_path(settings.payload_cache_path, page_key))
    raw_manifest = _load_json(_manifest_path(settings.payload_cache_path))
    _update_cache_index(raw_manifest)
    return build_api_manifest(raw_manifest)


def write_manifest_and_pages(manifest: dict[str, Any], pages: dict[str, dict[str, Any]]) -> ManifestResponse:
    settings = get_settings()
    ensure_payload_directories()
    manifest = {
        **manifest,
        "generated_at": manifest.get("generated_at") or now_iso(),
    }
    _write_json(_manifest_path(settings.payload_cache_path), manifest)
    for page_key, payload in pages.items():
        if page_key not in PAGE_KEYS:
            continue
        _write_json(_page_path(settings.payload_cache_path, page_key), payload)
    _update_cache_index(manifest)
    return build_api_manifest(manifest)
