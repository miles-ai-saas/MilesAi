"""异步生视频 Celery 任务。"""

from __future__ import annotations

import asyncio
from app.core.logging import get_logger
from uuid import UUID

from app.integrations.generative.jobs.errors import GenerativeJobCancelled, GenerativeJobNotFound
from app.integrations.generative.jobs.runner import (
    run_generative_image_job_async,
    run_generative_video_job_async,
)
from app.models.task.task_record import TaskStatus
from app.tenant.tasks.services.sync import sync_task_by_celery_id
from app.workers.app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    name="app.workers.tasks.generative.run_generative_video_job",
    bind=True,
    max_retries=0,
)
def run_generative_video_job(self, job_id: str) -> str:
    sync_task_by_celery_id(self.request.id, TaskStatus.RUNNING)
    try:
        asyncio.run(run_generative_video_job_async(UUID(job_id)))
        sync_task_by_celery_id(self.request.id, TaskStatus.SUCCESS)
        return "ok"
    except GenerativeJobCancelled:
        sync_task_by_celery_id(self.request.id, TaskStatus.CANCELLED, fail_reason="用户取消")
        return "cancelled"
    except GenerativeJobNotFound as exc:
        reason = str(exc)[:2000]
        sync_task_by_celery_id(self.request.id, TaskStatus.FAILED, fail_reason=reason)
        logger.exception("run_generative_video_job failed: %s", job_id)
        raise
    except Exception as exc:
        reason = str(exc)[:2000]
        sync_task_by_celery_id(self.request.id, TaskStatus.FAILED, fail_reason=reason)
        logger.exception("run_generative_video_job failed: %s", job_id)
        raise


@celery_app.task(
    name="app.workers.tasks.generative.run_generative_image_job",
    bind=True,
    max_retries=0,
)
def run_generative_image_job(self, job_id: str) -> str:
    sync_task_by_celery_id(self.request.id, TaskStatus.RUNNING)
    try:
        asyncio.run(run_generative_image_job_async(UUID(job_id)))
        sync_task_by_celery_id(self.request.id, TaskStatus.SUCCESS)
        return "ok"
    except GenerativeJobCancelled:
        sync_task_by_celery_id(self.request.id, TaskStatus.CANCELLED, fail_reason="用户取消")
        return "cancelled"
    except GenerativeJobNotFound as exc:
        reason = str(exc)[:2000]
        sync_task_by_celery_id(self.request.id, TaskStatus.FAILED, fail_reason=reason)
        logger.exception("run_generative_image_job failed: %s", job_id)
        raise
    except Exception as exc:
        reason = str(exc)[:2000]
        sync_task_by_celery_id(self.request.id, TaskStatus.FAILED, fail_reason=reason)
        logger.exception("run_generative_image_job failed: %s", job_id)
        raise
