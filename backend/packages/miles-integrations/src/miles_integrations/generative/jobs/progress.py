"""异步任务进度写入与取消检测（Worker / 轮询回调共用）。"""

from __future__ import annotations

import json
from uuid import UUID

from miles_common.redis_keys import RedisKeys
from miles_core.infra.db import AsyncSessionLocal
from miles_core.logging import get_logger
from miles_core.models.model.generative_job import GenerativeJob, GenerativeJobStatus
from miles_integrations.generative.jobs.errors import GenerativeJobCancelled

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
        from miles_core.infra.redis import get_redis

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
    """更新任务进度（percent 夹取到 0–100、message 截断 256 字符）并向 Redis 广播，供 SSE 即时感知。"""
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
    """任务是否已被取消（任务不存在时视为未取消）。"""
    async with AsyncSessionLocal() as db:
        job = await db.get(GenerativeJob, job_id)
        return job is not None and job.status == GenerativeJobStatus.CANCELLED


async def assert_generative_job_active(job_id: UUID) -> None:
    """任务已取消则抛 ``GenerativeJobCancelled``，让轮询/执行及时中断。"""
    if await is_generative_job_cancelled(job_id):
        raise GenerativeJobCancelled()


class GenerativeJobProgress:
    """厂商轮询阶段更新 DB 进度并响应取消。"""

    def __init__(self, job_id: UUID) -> None:
        self.job_id = job_id

    async def update(self, percent: int | None, message: str) -> None:
        """先确认任务未被取消，再写入进度并向 Redis 广播。"""
        await assert_generative_job_active(self.job_id)
        await update_generative_job_progress(
            self.job_id,
            percent=percent,
            message=message,
        )

    async def ensure_active(self) -> None:
        """任务已取消则抛 ``GenerativeJobCancelled``。"""
        await assert_generative_job_active(self.job_id)

    async def is_cancelled(self) -> bool:
        """查询任务是否已取消。"""
        return await is_generative_job_cancelled(self.job_id)
