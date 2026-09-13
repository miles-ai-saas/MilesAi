"""异步生图/生视频 Celery 任务。"""

from __future__ import annotations

import asyncio
from uuid import UUID

from miles_ai.integrations.generative.jobs.errors import GenerativeJobCancelled, GenerativeJobNotFound
from miles_core.infra.redis import reset_redis
from miles_core.jobs.tasks import TASK_NAMES
from miles_core.logging import get_logger
from miles_core.models.task.task_record import TaskStatus
from miles_portal.tenant.generative.services.job_execution import (
    run_generative_image_job_async,
    run_generative_video_job_async,
)
from miles_portal.tenant.tasks.services.sync import sync_task_by_celery_id
from miles_worker.app import celery_app

logger = get_logger(__name__)


def _run_coro(coro) -> None:
    """在独立事件循环中跑异步任务，结束后丢弃 Redis 单例以免绑到已关闭的 loop。"""
    try:
        asyncio.run(coro)
    finally:
        reset_redis()


@celery_app.task(
    name=TASK_NAMES["run_generative_video_job"],
    bind=True,
    max_retries=0,
)
def run_generative_video_job(self, job_id: str) -> str:
    """Celery 入口：跑异步生视频任务并同步 TaskRecord 状态；用户取消返回 ``cancelled``，异常记日志后重抛。"""
    sync_task_by_celery_id(self.request.id, TaskStatus.RUNNING)
    try:
        _run_coro(run_generative_video_job_async(UUID(job_id)))
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
    name=TASK_NAMES["run_generative_image_job"],
    bind=True,
    max_retries=0,
)
def run_generative_image_job(self, job_id: str) -> str:
    """Celery 入口：跑异步生图任务并同步 TaskRecord 状态；用户取消返回 ``cancelled``，异常记日志后重抛。"""
    sync_task_by_celery_id(self.request.id, TaskStatus.RUNNING)
    try:
        _run_coro(run_generative_image_job_async(UUID(job_id)))
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
