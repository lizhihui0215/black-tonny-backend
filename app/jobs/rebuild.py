from __future__ import annotations

import logging

from app.services import job_service, payload_service


logger = logging.getLogger(__name__)


def run_rebuild_job(job_id: str) -> None:
    try:
        job_service.update_job(
            job_id,
            status="running",
            message="正在刷新 payload 缓存。",
            started=True,
        )
        job_service.add_job_step(job_id, "读取样本数据", "running", "正在从 data/sample 复制 payload 到缓存目录。")
        manifest = payload_service.refresh_cache_from_sample()
        job_service.add_job_step(
            job_id,
            "生成缓存",
            "ok",
            f"已刷新缓存，批次 {manifest.analysis_batch_id or 'unknown'}。",
        )
        job_service.update_job(
            job_id,
            status="success",
            message="Payload 缓存已刷新。",
            finished=True,
        )
    except Exception as error:  # noqa: BLE001
        logger.exception("Rebuild job failed: %s", job_id)
        job_service.add_job_step(job_id, "执行失败", "error", str(error))
        job_service.update_job(
            job_id,
            status="error",
            message=f"重建失败：{error}",
            finished=True,
            last_error=str(error),
        )

