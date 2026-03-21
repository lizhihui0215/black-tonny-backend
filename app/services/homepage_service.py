from __future__ import annotations

import html
import json
from datetime import datetime
from typing import Any


POLL_INTERVAL_MS = 15000


def _escape(value: Any) -> str:
    if value is None:
        return "—"
    return html.escape(str(value))


def _format_time(value: Any) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(str(value)).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return _escape(value)


def _format_duration(seconds: Any) -> str:
    if seconds is None:
        return "—"
    total = max(0, int(float(seconds)))
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {minutes}m"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h"


def _format_bytes(num_bytes: Any) -> str:
    if num_bytes is None:
        return "—"
    value = float(num_bytes)
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024.0
        unit_index += 1
    return f"{value:.1f} {units[unit_index]}"


def _status_text(status: Any) -> str:
    mapping = {
        "operational": "正常",
        "warning": "警告",
        "degraded": "降级",
        "offline": "离线",
        "ok": "完成",
        "success": "成功",
        "running": "运行中",
        "queued": "排队中",
        "error": "异常",
        "info": "信息",
    }
    return mapping.get(str(status or "").lower(), _escape(status or "未知"))


def _render_component_card(component: dict[str, Any]) -> str:
    status = str(component.get("status") or "warning")
    label = _escape(component.get("label") or "未命名组件")
    detail = _escape(component.get("detail") or "暂无说明")
    return (
        '<article class="status-card">'
        f'<div class="status-card__top"><span class="status-pill status-pill--{_escape(status)}">{_status_text(status)}</span></div>'
        f"<h3>{label}</h3>"
        f"<p>{detail}</p>"
        "</article>"
    )


def _render_warning_list(warnings: list[str]) -> str:
    if not warnings:
        return '<div class="alert-stack"><div class="alert alert--ok">当前没有额外告警，服务处于可访问状态。</div></div>'
    items = "".join(f'<div class="alert alert--warning">{_escape(item)}</div>' for item in warnings)
    return f'<div class="alert-stack">{items}</div>'


def _render_key_value_rows(rows: list[tuple[str, str]]) -> str:
    return "".join(
        f'<div class="kv-row"><span class="kv-row__label">{_escape(label)}</span><strong>{value}</strong></div>'
        for label, value in rows
    )


def _render_panel(title: str, body: str, section_id: str | None = None, extra_class: str = "") -> str:
    id_attr = f' id="{section_id}"' if section_id else ""
    class_attr = " ".join(part for part in ("panel", extra_class) if part)
    return (
        f'<section{id_attr} class="{class_attr}">'
        f'<div class="panel__header"><h2>{_escape(title)}</h2></div>'
        f"{body}"
        "</section>"
    )


def _render_latest_job_card(latest_job: dict[str, Any] | None) -> str:
    if not latest_job:
        body = '<p class="empty-state">暂无重建任务记录。</p>'
    else:
        steps = latest_job.get("steps") or []
        step_items = "".join(
            (
                '<li class="timeline__item">'
                f'<span class="timeline__pill timeline__pill--{_escape(step.get("status") or "queued")}">{_status_text(step.get("status") or "queued")}</span>'
                f'<div><strong>{_escape(step.get("title") or "步骤")}</strong><p>{_escape(step.get("detail") or "暂无说明")}</p></div>'
                "</li>"
            )
            for step in steps[:3]
        )
        empty_step = '<li class="timeline__item"><div><p>暂无步骤。</p></div></li>'
        body = (
            '<div class="job-summary">'
            f'<div class="job-summary__hero"><span class="status-pill status-pill--{_escape(latest_job.get("status") or "warning")}">{_status_text(latest_job.get("status") or "warning")}</span>'
            f'<strong>{_escape(latest_job.get("message") or "暂无消息")}</strong></div>'
            '<div class="kv-grid">'
            f'<div class="kv-row"><span class="kv-row__label">任务 ID</span><strong>{_escape(latest_job.get("job_id"))}</strong></div>'
            f'<div class="kv-row"><span class="kv-row__label">创建时间</span><strong>{_format_time(latest_job.get("created_at"))}</strong></div>'
            f'<div class="kv-row"><span class="kv-row__label">开始时间</span><strong>{_format_time(latest_job.get("started_at"))}</strong></div>'
            f'<div class="kv-row"><span class="kv-row__label">结束时间</span><strong>{_format_time(latest_job.get("finished_at"))}</strong></div>'
            "</div>"
            f'<ul class="timeline">{step_items or empty_step}</ul>'
            "</div>"
        )
    return _render_panel("最近重建任务", body, section_id="latest-job-panel", extra_class="panel--job")


def _render_quick_links(links: list[dict[str, str]]) -> str:
    items = "".join(
        (
            '<a class="quick-link" href="{path}">'
            f'<strong>{_escape(link.get("label") or link.get("path") or "链接")}</strong>'
            f'<span>{_escape(link.get("description") or link.get("path") or "")}</span>'
            "</a>"
        ).format(path=html.escape(str(link.get("path") or "#"), quote=True))
        for link in links
    )
    return _render_panel("快速入口", f'<div id="quick-links-grid" class="quick-links">{items}</div>', extra_class="panel--links")


def render_homepage(status: dict[str, Any]) -> str:
    runtime = status.get("runtime") or {}
    system = status.get("system") or {}
    manifest = status.get("manifest") or {}
    latest_job = status.get("latest_job")
    components = status.get("components") or {}
    quick_links = status.get("quick_links") or []
    mode_warnings = status.get("mode_warnings") or []
    cache_summary = status.get("cache_summary") or {}
    database_summary = status.get("database_summary") or {}

    component_cards = "".join(_render_component_card(component) for component in components.values())
    runtime_rows = _render_key_value_rows(
        [
            ("当前时间", _format_time(runtime.get("current_time"))),
            ("主机名", _escape(runtime.get("hostname"))),
            ("平台", _escape(runtime.get("platform"))),
            ("Python", _escape(runtime.get("python_version"))),
            ("进程 PID", _escape(runtime.get("process_id"))),
            ("运行时长", _format_duration(runtime.get("process_uptime_seconds"))),
            ("CPU 核心数", _escape(runtime.get("cpu_count"))),
        ]
    )
    system_rows = _render_key_value_rows(
        [
            ("Load Average", _escape(system.get("load_avg_text"))),
            ("磁盘总量", _format_bytes(system.get("disk_total_bytes"))),
            ("磁盘已用", _format_bytes(system.get("disk_used_bytes"))),
            ("磁盘可用", _format_bytes(system.get("disk_free_bytes"))),
            ("磁盘使用率", _escape(system.get("disk_percent_text"))),
            ("数据库表计数", _escape(database_summary.get("table_counts_text"))),
        ]
    )
    business_rows = _render_key_value_rows(
        [
            ("门店", _escape(cache_summary.get("store_name") or manifest.get("store_name"))),
            ("分析批次", _escape(cache_summary.get("analysis_batch_id") or manifest.get("analysis_batch_id"))),
            ("生成时间", _format_time(cache_summary.get("generated_at") or manifest.get("generated_at"))),
            ("重建计划", _escape(status.get("rebuild_cron"))),
            ("缓存来源", _escape(cache_summary.get("source_mode"))),
            ("页面数量", f"{_escape(cache_summary.get('page_count'))} / {_escape(cache_summary.get('expected_page_count'))}"),
        ]
    )
    warnings_html = _render_warning_list(mode_warnings)
    latest_job_card = _render_latest_job_card(latest_job)
    quick_links_card = _render_quick_links(quick_links)

    load_avg_ratio = float(system.get("load_avg_ratio") or 0.0)
    load_avg_bar = min(max(load_avg_ratio * 100, 0.0), 100.0)
    disk_bar = min(max(float(system.get("disk_percent") or 0.0), 0.0), 100.0)
    status_json = json.dumps(status, ensure_ascii=False).replace("</", "<\\/")

    template = """
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>__TITLE__</title>
        <style>
          :root {
            color-scheme: light;
            --bg: #eef3f8;
            --panel: rgba(255,255,255,0.92);
            --panel-border: rgba(16,24,40,0.08);
            --text: #102030;
            --muted: #5f6f82;
            --brand: #0b6bcb;
            --brand-soft: #dceeff;
            --ok: #108043;
            --ok-soft: #def7e5;
            --warn: #b98900;
            --warn-soft: #fff2cc;
            --danger: #c0352b;
            --danger-soft: #fde8e7;
          }
          * {
            box-sizing: border-box;
          }
          body {
            margin: 0;
            min-height: 100vh;
            font-family: "SF Pro Display", "PingFang SC", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background:
              radial-gradient(circle at top left, rgba(41, 128, 255, 0.18), transparent 22%),
              radial-gradient(circle at top right, rgba(29, 202, 157, 0.14), transparent 26%),
              linear-gradient(180deg, #f5f8fc 0%, #eef3f8 100%);
            color: var(--text);
          }
          a {
            color: inherit;
            text-decoration: none;
          }
          .shell {
            max-width: 1320px;
            margin: 0 auto;
            padding: 32px 24px 56px;
          }
          .hero {
            position: relative;
            overflow: hidden;
            border-radius: 28px;
            padding: 28px;
            color: #fff;
            background:
              linear-gradient(135deg, rgba(8, 30, 61, 0.96), rgba(14, 78, 130, 0.94)),
              linear-gradient(45deg, rgba(24, 145, 255, 0.36), rgba(57, 203, 136, 0.2));
            box-shadow: 0 30px 60px rgba(15, 23, 42, 0.16);
          }
          .hero::after {
            content: "";
            position: absolute;
            inset: auto -10% -45% auto;
            width: 360px;
            height: 360px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(255,255,255,0.18), transparent 60%);
          }
          .hero__top {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 24px;
            flex-wrap: wrap;
          }
          .hero h1 {
            margin: 0 0 8px;
            font-size: clamp(30px, 4vw, 42px);
            letter-spacing: -0.02em;
          }
          .hero p {
            margin: 0;
            max-width: 760px;
            color: rgba(255,255,255,0.82);
            line-height: 1.7;
          }
          .hero__meta {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 18px;
          }
          .tag {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            border-radius: 999px;
            font-size: 13px;
            font-weight: 600;
            background: rgba(255,255,255,0.12);
            border: 1px solid rgba(255,255,255,0.16);
          }
          .hero__stats {
            display: grid;
            grid-template-columns: repeat(2, minmax(140px, 1fr));
            gap: 12px;
            min-width: min(100%, 340px);
          }
          .hero-stat {
            padding: 16px 18px;
            border-radius: 18px;
            background: rgba(255,255,255,0.12);
            border: 1px solid rgba(255,255,255,0.14);
          }
          .hero-stat span {
            display: block;
            font-size: 12px;
            color: rgba(255,255,255,0.72);
            margin-bottom: 8px;
          }
          .hero-stat strong {
            display: block;
            font-size: 18px;
          }
          .alert-stack {
            display: grid;
            gap: 12px;
            margin-top: 24px;
          }
          .alert {
            padding: 14px 16px;
            border-radius: 16px;
            font-size: 14px;
            line-height: 1.6;
          }
          .alert--warning {
            background: var(--warn-soft);
            color: #7b5b00;
            border: 1px solid rgba(185, 137, 0, 0.18);
          }
          .alert--ok {
            background: var(--ok-soft);
            color: #0f6f3a;
            border: 1px solid rgba(16, 128, 67, 0.14);
          }
          .grid {
            display: grid;
            gap: 20px;
            margin-top: 24px;
          }
          .status-grid {
            grid-template-columns: repeat(5, minmax(0, 1fr));
          }
          .panel-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
          .panel {
            background: var(--panel);
            border: 1px solid var(--panel-border);
            border-radius: 24px;
            padding: 22px;
            box-shadow: 0 22px 50px rgba(15, 23, 42, 0.05);
            backdrop-filter: blur(14px);
          }
          .panel__header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 18px;
          }
          .panel h2, .status-card h3 {
            margin: 0;
            font-size: 18px;
          }
          .panel p, .status-card p, .timeline p, .quick-link span {
            margin: 0;
            line-height: 1.6;
            color: var(--muted);
          }
          .status-card {
            background: var(--panel);
            border: 1px solid var(--panel-border);
            border-radius: 22px;
            padding: 20px;
            box-shadow: 0 16px 40px rgba(15, 23, 42, 0.05);
          }
          .status-card__top {
            display: flex;
            justify-content: flex-end;
            margin-bottom: 14px;
          }
          .status-pill {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 88px;
            padding: 6px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.05em;
          }
          .status-pill--operational, .status-pill--ok, .status-pill--success,
          .timeline__pill--ok, .timeline__pill--success {
            color: var(--ok);
            background: var(--ok-soft);
          }
          .status-pill--warning, .status-pill--queued, .status-pill--running,
          .timeline__pill--warning, .timeline__pill--queued, .timeline__pill--running {
            color: #8a6700;
            background: var(--warn-soft);
          }
          .status-pill--degraded, .status-pill--offline, .status-pill--error,
          .timeline__pill--degraded, .timeline__pill--offline, .timeline__pill--error {
            color: var(--danger);
            background: var(--danger-soft);
          }
          .kv-grid {
            display: grid;
            gap: 12px;
          }
          .kv-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 18px;
            padding: 12px 14px;
            background: rgba(255,255,255,0.74);
            border: 1px solid rgba(16,24,40,0.05);
            border-radius: 16px;
          }
          .kv-row__label {
            color: var(--muted);
            font-size: 13px;
          }
          .progress-list {
            display: grid;
            gap: 14px;
            margin-bottom: 18px;
          }
          .progress-item {
            display: grid;
            gap: 8px;
          }
          .progress-meta {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            color: var(--muted);
            font-size: 13px;
          }
          .progress-bar {
            width: 100%;
            height: 10px;
            border-radius: 999px;
            background: #e6edf5;
            overflow: hidden;
          }
          .progress-bar__value {
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, #1f6feb, #2bb673);
          }
          .timeline {
            margin: 18px 0 0;
            padding: 0;
            list-style: none;
            display: grid;
            gap: 12px;
          }
          .timeline__item {
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 12px;
            align-items: start;
            padding: 12px 14px;
            border-radius: 16px;
            background: rgba(255,255,255,0.7);
            border: 1px solid rgba(16,24,40,0.05);
          }
          .timeline__pill {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 4px 8px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 700;
          }
          .job-summary {
            display: grid;
            gap: 18px;
          }
          .job-summary__hero {
            display: grid;
            gap: 12px;
          }
          .quick-links {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 14px;
          }
          .quick-link {
            padding: 16px 18px;
            border-radius: 18px;
            background: linear-gradient(180deg, rgba(255,255,255,0.92), rgba(238,243,248,0.9));
            border: 1px solid rgba(16,24,40,0.06);
            display: grid;
            gap: 6px;
          }
          .empty-state {
            color: var(--muted);
          }
          @media (max-width: 1200px) {
            .status-grid {
              grid-template-columns: repeat(3, minmax(0, 1fr));
            }
          }
          @media (max-width: 860px) {
            .hero__stats,
            .status-grid,
            .panel-grid,
            .quick-links {
              grid-template-columns: 1fr;
            }
            .shell {
              padding: 20px 16px 40px;
            }
            .hero {
              padding: 22px;
            }
          }
        </style>
      </head>
      <body>
        <main class="shell">
          <section class="hero">
            <div class="hero__top">
              <div>
                <h1>__APP_NAME__</h1>
                <p>后端首页现在展示的是轻量运维驾驶舱：你可以直接看到服务状态、数据库、缓存来源、最近任务和关键 API 入口，而不是一张空说明页。</p>
                <div class="hero__meta" id="hero-meta">__HERO_META__</div>
              </div>
              <div class="hero__stats">
                <div class="hero-stat">
                  <span>缓存来源</span>
                  <strong id="hero-source-mode">__HERO_SOURCE_MODE__</strong>
                </div>
                <div class="hero-stat">
                  <span>页面数量</span>
                  <strong id="hero-page-count">__HERO_PAGE_COUNT__</strong>
                </div>
                <div class="hero-stat">
                  <span>最近任务</span>
                  <strong id="hero-latest-job">__HERO_LATEST_JOB__</strong>
                </div>
                <div class="hero-stat">
                  <span>数据库</span>
                  <strong id="hero-database-name">__HERO_DATABASE_NAME__</strong>
                </div>
              </div>
            </div>
            <div id="warning-stack">__WARNINGS__</div>
          </section>

          <section class="grid status-grid" id="components-grid">__COMPONENTS__</section>

          <section class="grid panel-grid">
            __RUNTIME_PANEL__
            <section id="system-panel" class="panel">
              <div class="panel__header"><h2>系统概况</h2></div>
              <div class="progress-list">
                <div class="progress-item">
                  <div class="progress-meta"><span>Load Average</span><strong id="system-load-text">__LOAD_TEXT__</strong></div>
                  <div class="progress-bar"><div id="system-load-bar" class="progress-bar__value" style="width: __LOAD_BAR__%"></div></div>
                </div>
                <div class="progress-item">
                  <div class="progress-meta"><span>磁盘占用</span><strong id="system-disk-text">__DISK_TEXT__</strong></div>
                  <div class="progress-bar"><div id="system-disk-bar" class="progress-bar__value" style="width: __DISK_BAR__%"></div></div>
                </div>
              </div>
              <div id="system-kv" class="kv-grid">__SYSTEM_ROWS__</div>
            </section>
            __BUSINESS_PANEL__
            __LATEST_JOB_PANEL__
            __QUICK_LINKS_PANEL__
          </section>
        </main>
        <script>
          const INITIAL_STATUS = __STATUS_JSON__;
          const POLL_INTERVAL_MS = __POLL_INTERVAL_MS__;

          function escapeHtml(value) {
            if (value === null || value === undefined || value === '') return '—';
            return String(value)
              .replaceAll('&', '&amp;')
              .replaceAll('<', '&lt;')
              .replaceAll('>', '&gt;')
              .replaceAll('"', '&quot;')
              .replaceAll("'", '&#39;');
          }

          function statusText(status) {
            const mapping = {
              operational: '正常',
              warning: '警告',
              degraded: '降级',
              offline: '离线',
              success: '成功',
              running: '运行中',
              queued: '排队中',
              error: '异常',
              info: '信息',
            };
            return mapping[String(status || '').toLowerCase()] || escapeHtml(status || '未知');
          }

          function formatTime(value) {
            if (!value) return '—';
            const date = new Date(value);
            if (Number.isNaN(date.getTime())) return escapeHtml(value);
            return date.toLocaleString('zh-CN', { hour12: false });
          }

          function formatDuration(seconds) {
            if (seconds === null || seconds === undefined) return '—';
            let total = Math.max(0, Math.floor(Number(seconds)));
            if (total < 60) return `${total}s`;
            const mins = Math.floor(total / 60);
            const secs = total % 60;
            if (mins < 60) return `${mins}m ${secs}s`;
            const hours = Math.floor(mins / 60);
            const restMins = mins % 60;
            if (hours < 24) return `${hours}h ${restMins}m`;
            const days = Math.floor(hours / 24);
            const restHours = hours % 24;
            return `${days}d ${restHours}h`;
          }

          function formatBytes(bytes) {
            if (bytes === null || bytes === undefined) return '—';
            let value = Number(bytes);
            const units = ['B', 'KB', 'MB', 'GB', 'TB'];
            let index = 0;
            while (value >= 1024 && index < units.length - 1) {
              value /= 1024;
              index += 1;
            }
            return `${value.toFixed(1)} ${units[index]}`;
          }

          function renderWarnings(warnings) {
            if (!warnings || warnings.length === 0) {
              return '<div class="alert-stack"><div class="alert alert--ok">当前没有额外告警，服务处于可访问状态。</div></div>';
            }
            return `<div class="alert-stack">${warnings.map((item) => `<div class="alert alert--warning">${escapeHtml(item)}</div>`).join('')}</div>`;
          }

          function renderComponents(components) {
            return Object.values(components || {}).map((component) => `
              <article class="status-card">
                <div class="status-card__top">
                  <span class="status-pill status-pill--${escapeHtml(component.status || 'warning')}">${statusText(component.status || 'warning')}</span>
                </div>
                <h3>${escapeHtml(component.label || '未命名组件')}</h3>
                <p>${escapeHtml(component.detail || '暂无说明')}</p>
              </article>
            `).join('');
          }

          function renderRows(rows) {
            return rows.map(([label, value]) => `
              <div class="kv-row">
                <span class="kv-row__label">${escapeHtml(label)}</span>
                <strong>${value}</strong>
              </div>
            `).join('');
          }

          function renderJob(latestJob) {
            if (!latestJob) {
              return '<p class="empty-state">暂无重建任务记录。</p>';
            }
            const steps = (latestJob.steps || []).slice(0, 3).map((step) => `
              <li class="timeline__item">
                <span class="timeline__pill timeline__pill--${escapeHtml(step.status || 'queued')}">${statusText(step.status || 'queued')}</span>
                <div><strong>${escapeHtml(step.title || '步骤')}</strong><p>${escapeHtml(step.detail || '暂无说明')}</p></div>
              </li>
            `).join('') || '<li class="timeline__item"><div><p>暂无步骤。</p></div></li>';

            return `
              <div class="job-summary">
                <div class="job-summary__hero">
                  <span class="status-pill status-pill--${escapeHtml(latestJob.status || 'warning')}">${statusText(latestJob.status || 'warning')}</span>
                  <strong>${escapeHtml(latestJob.message || '暂无消息')}</strong>
                </div>
                <div class="kv-grid">
                  <div class="kv-row"><span class="kv-row__label">任务 ID</span><strong>${escapeHtml(latestJob.job_id)}</strong></div>
                  <div class="kv-row"><span class="kv-row__label">创建时间</span><strong>${formatTime(latestJob.created_at)}</strong></div>
                  <div class="kv-row"><span class="kv-row__label">开始时间</span><strong>${formatTime(latestJob.started_at)}</strong></div>
                  <div class="kv-row"><span class="kv-row__label">结束时间</span><strong>${formatTime(latestJob.finished_at)}</strong></div>
                </div>
                <ul class="timeline">${steps}</ul>
              </div>
            `;
          }

          function renderStatus(status) {
            const runtime = status.runtime || {};
            const system = status.system || {};
            const cache = status.cache_summary || {};
            const db = status.database_summary || {};
            const manifest = status.manifest || {};

            document.getElementById('hero-meta').innerHTML = `
              <span class="tag">环境：${escapeHtml(status.app_env)}</span>
              <span class="tag">时区：${escapeHtml(status.timezone)}</span>
              <span class="tag">当前时间：${formatTime(runtime.current_time)}</span>
            `;
            document.getElementById('hero-source-mode').textContent = cache.source_mode || '—';
            document.getElementById('hero-page-count').textContent = `${cache.page_count ?? '—'} / ${cache.expected_page_count ?? '—'}`;
            document.getElementById('hero-latest-job').textContent = statusText((status.latest_job || {}).status || '暂无');
            document.getElementById('hero-database-name').textContent = db.database_name || '—';
            document.getElementById('warning-stack').innerHTML = renderWarnings(status.mode_warnings || []);
            document.getElementById('components-grid').innerHTML = renderComponents(status.components || {});

            document.getElementById('runtime-kv').innerHTML = renderRows([
              ['当前时间', formatTime(runtime.current_time)],
              ['主机名', escapeHtml(runtime.hostname)],
              ['平台', escapeHtml(runtime.platform)],
              ['Python', escapeHtml(runtime.python_version)],
              ['进程 PID', escapeHtml(runtime.process_id)],
              ['运行时长', formatDuration(runtime.process_uptime_seconds)],
              ['CPU 核心数', escapeHtml(runtime.cpu_count)],
            ]);

            document.getElementById('system-load-text').textContent = system.load_avg_text || '—';
            document.getElementById('system-load-bar').style.width = `${Math.min(Math.max((system.load_avg_ratio || 0) * 100, 0), 100)}%`;
            document.getElementById('system-disk-text').textContent = system.disk_percent_text || '—';
            document.getElementById('system-disk-bar').style.width = `${Math.min(Math.max(system.disk_percent || 0, 0), 100)}%`;
            document.getElementById('system-kv').innerHTML = renderRows([
              ['Load Average', escapeHtml(system.load_avg_text)],
              ['磁盘总量', formatBytes(system.disk_total_bytes)],
              ['磁盘已用', formatBytes(system.disk_used_bytes)],
              ['磁盘可用', formatBytes(system.disk_free_bytes)],
              ['磁盘使用率', escapeHtml(system.disk_percent_text)],
              ['数据库表计数', escapeHtml(db.table_counts_text)],
            ]);

            document.getElementById('business-kv').innerHTML = renderRows([
              ['门店', escapeHtml(cache.store_name || manifest.store_name)],
              ['分析批次', escapeHtml(cache.analysis_batch_id || manifest.analysis_batch_id)],
              ['生成时间', formatTime(cache.generated_at || manifest.generated_at)],
              ['重建计划', escapeHtml(status.rebuild_cron)],
              ['缓存来源', escapeHtml(cache.source_mode)],
              ['页面数量', `${cache.page_count ?? '—'} / ${cache.expected_page_count ?? '—'}`],
            ]);

            document.getElementById('latest-job-body').innerHTML = renderJob(status.latest_job || null);
          }

          async function refreshStatus() {
            try {
              const response = await fetch('/api/status', { headers: { Accept: 'application/json' } });
              if (!response.ok) throw new Error(`HTTP ${response.status}`);
              const payload = await response.json();
              renderStatus(payload);
            } catch (error) {
              const warningStack = document.getElementById('warning-stack');
              warningStack.innerHTML = renderWarnings([`状态轮询失败：${error.message}`]);
            }
          }

          renderStatus(INITIAL_STATUS);
          window.setInterval(refreshStatus, POLL_INTERVAL_MS);
        </script>
      </body>
    </html>
    """

    replacements = {
        "__TITLE__": _escape(status.get("app_name") or "Black Tonny Backend"),
        "__APP_NAME__": _escape(status.get("app_name") or "Black Tonny Backend"),
        "__HERO_META__": (
            f'<span class="tag">环境：{_escape(status.get("app_env"))}</span>'
            f'<span class="tag">时区：{_escape(status.get("timezone"))}</span>'
            f'<span class="tag">当前时间：{_format_time(runtime.get("current_time"))}</span>'
        ),
        "__HERO_SOURCE_MODE__": _escape(cache_summary.get("source_mode")),
        "__HERO_PAGE_COUNT__": f"{_escape(cache_summary.get('page_count'))} / {_escape(cache_summary.get('expected_page_count'))}",
        "__HERO_LATEST_JOB__": _status_text((latest_job or {}).get("status") or "暂无"),
        "__HERO_DATABASE_NAME__": _escape(database_summary.get("database_name")),
        "__WARNINGS__": warnings_html,
        "__COMPONENTS__": component_cards,
        "__RUNTIME_PANEL__": _render_panel(
            "运行时信息",
            f'<div id="runtime-kv" class="kv-grid">{runtime_rows}</div>',
        ),
        "__LOAD_TEXT__": _escape(system.get("load_avg_text")),
        "__LOAD_BAR__": f"{load_avg_bar:.1f}",
        "__DISK_TEXT__": _escape(system.get("disk_percent_text")),
        "__DISK_BAR__": f"{disk_bar:.1f}",
        "__SYSTEM_ROWS__": system_rows,
        "__BUSINESS_PANEL__": _render_panel(
            "业务上下文",
            f'<div id="business-kv" class="kv-grid">{business_rows}</div>',
        ),
        "__LATEST_JOB_PANEL__": latest_job_card.replace('<div class="job-summary">', '<div id="latest-job-body" class="job-summary">', 1)
        if 'class="job-summary"' in latest_job_card
        else latest_job_card.replace('<p class="empty-state">', '<div id="latest-job-body"><p class="empty-state">', 1).replace(
            "</p>", "</p></div>", 1
        ),
        "__QUICK_LINKS_PANEL__": quick_links_card,
        "__STATUS_JSON__": status_json,
        "__POLL_INTERVAL_MS__": str(POLL_INTERVAL_MS),
    }

    html_output = template
    for placeholder, value in replacements.items():
        html_output = html_output.replace(placeholder, value)
    return html_output
