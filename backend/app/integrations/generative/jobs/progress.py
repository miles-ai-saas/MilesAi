"""异步任务进度写入与取消检测（Worker / 轮询回调共用）。"""

from __future__ import annotations

import json
from uuid import UUID

from app.core.logging import get_logger
from app.infra.db import AsyncSessionLocal
from app.integrations.generative.jobs.errors import GenerativeJobCancelled
from app.models.model.generative_job import GenerativeJob, GenerativeJobStatus
from app.utils.redis_keys import RedisKeys

logger = get_logger(__name__)


async def publish_generative_job_update(
    tenant_id: UUID | str,
    job_id: UUID | str,
    *,
    status: str,
    percent: int | None = None,
    message: str | None = None,
) -> None:
    """向 Redis Pub/Sub 频道发布任务进度变更通知。"""
    try:
        from app.infra.redis import get_redis

        redis = get_redis()
        channel = RedisKeys.generative_job_progress(str(tenant_id), str(job_id))
        await redis.publish(
            channel,
            json.dumps(
                {
                    "job_id": str(job_id),
                    "status": status,
                    "percent": percent,
                    "message": message,
                },
                ensure_ascii=False,
            ),
        )
    except Exception:
        logger.debug("Redis 发布 job %s 进度通知失败", job_id, exc_info=True)


async def update_generative_job_progress(
    job_id: UUID,
    *,
    percent: int | None = None,
    message: str | None = None,
) -> None:
    async with AsyncSessionLocal() as db:
        job = await db.get(GenerativeJob, job_id)
        if not job:
            return
        if percent is not None:
            job.progress_percent = max(0, min(100, int(percent)))
        if message is not None:
            job.progress_message = message[:256]
        await db.commit()
        # 发布 Redis 通知，SSE 端点可即时感知进度变化
        await publish_generative_job_update(
            job.tenant_id,
            job_id,
            status=job.status.value,
            percent=job.progress_percent,
            message=job.progress_message,
        )


async def is_generative_job_cancelled(job_id: UUID) -> bool:
    async with AsyncSessionLocal() as db:
        job = await db.get(GenerativeJob, job_id)
        return job is not None and job.status == GenerativeJobStatus.CANCELLED


async def assert_generative_job_active(job_id: UUID) -> None:
    if await is_generative_job_cancelled(job_id):
        raise GenerativeJobCancelled()


class GenerativeJobProgress:
    """厂商轮询阶段更新 DB 进度并响应取消。"""

    def __init__(self, job_id: UUID) -> None:
        self.job_id = job_id

    async def update(self, percent: int | None, message: str) -> None:
        await assert_generative_job_active(self.job_id)
        await update_generative_job_progress(
            self.job_id,
            percent=percent,
            message=message,
        )

    async def ensure_active(self) -> None:
        await assert_generative_job_active(self.job_id)

    async def is_cancelled(self) -> bool:
        return await is_generative_job_cancelled(self.job_id)
