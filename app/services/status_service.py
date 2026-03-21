from __future__ import annotations

import os
import platform
import shutil
import socket
import sys
import time
from typing import Optional

from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.core.timezone import now_iso
from app.db.base import (
    analysis_batches,
    capture_batches,
    capture_endpoint_payloads,
    cost_snapshots,
    inventory_current,
    inventory_daily_snapshot,
    job_runs,
    job_steps,
    payload_cache_index,
    sales_order_items,
    sales_orders,
)
from app.db.engine import get_capture_engine, get_serving_engine
from app.schemas.manifest import ManifestResponse
from app.services import job_service, payload_service


PROCESS_STARTED_AT = time.time()


def _build_runtime_summary() -> dict[str, object]:
    return {
        "current_time": now_iso(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
        "process_id": os.getpid(),
        "process_uptime_seconds": max(0, int(time.time() - PROCESS_STARTED_AT)),
        "cpu_count": os.cpu_count(),
    }


def _build_system_summary(project_root: str) -> dict[str, object]:
    usage = shutil.disk_usage(project_root)
    disk_percent = round((usage.used / usage.total) * 100, 1) if usage.total else 0.0
    load_avg = None
    load_avg_ratio = None
    if hasattr(os, "getloadavg"):
        try:
            load_avg = os.getloadavg()
            cpu_count = os.cpu_count() or 1
            load_avg_ratio = round(float(load_avg[0]) / float(cpu_count), 3)
        except OSError:
            load_avg = None
            load_avg_ratio = None

    return {
        "load_avg": list(load_avg) if load_avg else None,
        "load_avg_text": " / ".join(f"{value:.2f}" for value in load_avg) if load_avg else "不可用",
        "load_avg_ratio": load_avg_ratio,
        "disk_total_bytes": usage.total,
        "disk_used_bytes": usage.used,
        "disk_free_bytes": usage.free,
        "disk_percent": disk_percent,
        "disk_percent_text": f"{disk_percent:.1f}%",
    }


def _build_single_database_summary(engine, table_map: dict[str, object]) -> dict[str, object]:
    summary: dict[str, object] = {
        "connected": False,
        "database_name": engine.url.database,
        "dialect": engine.dialect.name,
        "driver": engine.dialect.driver,
        "table_counts": {name: 0 for name in table_map},
        "table_counts_text": " / ".join("0" for _ in table_map),
    }

    try:
        with engine.begin() as connection:
            connection.execute(text("SELECT 1"))
            counts = {
                name: int(connection.execute(select(func.count()).select_from(table)).scalar_one())
                for name, table in table_map.items()
            }
        summary["connected"] = True
        summary["table_counts"] = counts
        summary["table_counts_text"] = " / ".join(str(counts[key]) for key in table_map)
    except Exception as error:  # noqa: BLE001
        summary["error"] = str(error)

    return summary


def _build_database_summary() -> dict[str, object]:
    serving_summary = _build_single_database_summary(
        get_serving_engine(),
        {
            "job_runs": job_runs,
            "job_steps": job_steps,
            "cost_snapshots": cost_snapshots,
            "payload_cache_index": payload_cache_index,
            "analysis_batches": analysis_batches,
            "sales_orders": sales_orders,
            "sales_order_items": sales_order_items,
            "inventory_current": inventory_current,
            "inventory_daily_snapshot": inventory_daily_snapshot,
        },
    )
    capture_summary = _build_single_database_summary(
        get_capture_engine(),
        {
            "capture_batches": capture_batches,
            "capture_endpoint_payloads": capture_endpoint_payloads,
        },
    )
    return {
        "connected": bool(serving_summary.get("connected")) and bool(capture_summary.get("connected")),
        "table_counts_text": (
            f"serving[{serving_summary.get('table_counts_text')}] | "
            f"capture[{capture_summary.get('table_counts_text')}]"
        ),
        "serving": serving_summary,
        "capture": capture_summary,
    }


def _build_components(
    database_summary: dict[str, object],
    cache_summary: dict[str, object],
    latest_job: dict[str, object] | None,
) -> dict[str, dict[str, str]]:
    serving_summary = database_summary.get("serving") or {}
    capture_summary = database_summary.get("capture") or {}
    serving_connected = bool(serving_summary.get("connected"))
    capture_connected = bool(capture_summary.get("connected"))
    serving_dialect = str(serving_summary.get("dialect") or "")
    capture_dialect = str(capture_summary.get("dialect") or "")
    source_mode = str(cache_summary.get("source_mode") or "unknown")
    page_count = int(cache_summary.get("page_count") or 0)
    expected_page_count = int(cache_summary.get("expected_page_count") or 0)

    both_mysql = serving_dialect == "mysql" and capture_dialect == "mysql"
    mysql_status = (
        "operational"
        if serving_connected and capture_connected and both_mysql
        else "warning"
        if serving_connected or capture_connected
        else "offline"
    )
    if serving_connected and capture_connected:
        mysql_detail = (
            f"Serving={serving_summary.get('database_name') or 'unknown'} / "
            f"Capture={capture_summary.get('database_name') or 'unknown'}"
        )
    elif serving_connected or capture_connected:
        mysql_detail = (
            f"Serving={serving_summary.get('database_name') or 'offline'} / "
            f"Capture={capture_summary.get('database_name') or 'offline'}"
        )
    else:
        mysql_detail = "Serving 与 Capture 数据库都不可用"

    if source_mode == "cache" and page_count >= expected_page_count > 0:
        cache_status = "operational"
        cache_detail = f"缓存已就绪，页面 {page_count}/{expected_page_count}"
    elif source_mode == "sample":
        cache_status = "warning"
        cache_detail = f"当前直接读取样本数据，页面 {page_count}/{expected_page_count}"
    else:
        cache_status = "degraded"
        cache_detail = f"缓存不完整，页面 {page_count}/{expected_page_count}"

    latest_job_status = "warning"
    latest_job_detail = "暂无重建任务记录"
    if latest_job:
        raw_status = str(latest_job.get("status") or "")
        if raw_status == "success":
            latest_job_status = "operational"
        elif raw_status in {"queued", "running"}:
            latest_job_status = "warning"
        elif raw_status == "error":
            latest_job_status = "degraded"
        latest_job_detail = str(latest_job.get("message") or "最近任务已记录")

    analysis_status = "warning" if source_mode in {"sample", "cache"} else "operational"
    analysis_detail = (
        "当前仍处于 sample/cache 引导模式，尚未接入真实分析链"
        if source_mode in {"sample", "cache"}
        else "当前分析来源正常"
    )

    return {
        "api": {
            "status": "operational",
            "label": "API 服务",
            "detail": "接口服务已启动，可访问 /api/health 和 /api/status",
        },
        "mysql": {
            "status": mysql_status,
            "label": "MySQL",
            "detail": mysql_detail,
        },
        "payload_cache": {
            "status": cache_status,
            "label": "Payload Cache",
            "detail": cache_detail,
        },
        "latest_job": {
            "status": latest_job_status,
            "label": "最近重建任务",
            "detail": latest_job_detail,
        },
        "analysis_source": {
            "status": analysis_status,
            "label": "分析来源",
            "detail": analysis_detail,
        },
    }


def _build_quick_links() -> list[dict[str, str]]:
    return [
        {"label": "接口文档", "path": "/docs", "description": "Swagger 文档与调试入口"},
        {"label": "ReDoc 文档", "path": "/redoc", "description": "ReDoc 风格接口文档入口"},
        {"label": "健康检查", "path": "/api/health", "description": "确认服务是否可访问"},
        {"label": "状态总览", "path": "/api/status", "description": "服务、数据库、缓存与任务摘要"},
        {"label": "页面清单", "path": "/api/manifest", "description": "前端页面入口清单"},
        {"label": "经营总览 Payload", "path": "/api/pages/dashboard", "description": "直接查看 dashboard JSON"},
        {"label": "顶部 Summary", "path": "/api/dashboard/summary?preset=last7days", "description": "查看 Dashboard 顶部 8 张卡片接口"},
    ]


def get_status() -> dict[str, object]:
    settings = get_settings()
    runtime = _build_runtime_summary()
    system = _build_system_summary(str(settings.project_root))
    database_summary = _build_database_summary()
    cache_summary = payload_service.get_payload_cache_summary()
    latest_job = None
    try:
        latest_job = job_service.get_latest_job()
    except Exception:  # noqa: BLE001
        latest_job = None
    manifest: Optional[ManifestResponse] = None
    try:
        manifest = payload_service.get_manifest()
    except FileNotFoundError:
        manifest = None
    latest_job_payload = latest_job.model_dump() if latest_job else None

    mode_warnings = []
    if settings.app_env != "production":
        mode_warnings.append(f"当前运行在 {settings.app_env} 环境，更适合开发与联调。")
    if cache_summary.get("source_mode") in {"sample", "cache"}:
        mode_warnings.append("当前页面 payload 仍来自 sample/cache 引导模式，还没有接入真实分析链。")
    if not database_summary.get("connected"):
        mode_warnings.append("数据库连接不可用，首页只展示降级状态。")

    return {
        "ok": True,
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "timezone": settings.app_timezone,
        "rebuild_cron": settings.rebuild_cron,
        "runtime": runtime,
        "system": system,
        "components": _build_components(database_summary, cache_summary, latest_job_payload),
        "cache_summary": cache_summary,
        "database_summary": database_summary,
        "quick_links": _build_quick_links(),
        "mode_warnings": mode_warnings,
        "manifest": manifest.model_dump() if manifest else None,
        "latest_job": latest_job_payload,
    }
