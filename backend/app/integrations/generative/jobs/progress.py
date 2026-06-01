"""异步任务进度写入与取消检测（Worker / 轮询回调共用）。"""

from __future__ import annotations

from uuid import UUID

from app.infra.db import AsyncSessionLocal
from app.integrations.generative.jobs.errors import GenerativeJobCancelled
from app.models.model.generative_job import GenerativeJob, GenerativeJobStatus


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
