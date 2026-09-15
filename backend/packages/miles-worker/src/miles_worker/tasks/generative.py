"""异步生图/生视频 Celery 任务。"""

from __future__ import annotations

from uuid import UUID

from miles_ai.integrations.generative.jobs.errors import GenerativeJobCancelled
from miles_core.infra.db import run_worker_db_coro
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
    """在独立事件循环中跑异步任务；DB engine 由包装在关闭 loop 前释放。"""
    try:
        run_worker_db_coro(coro)
    finally:
        reset_redis()


def _run_generative_task(self, job_id: str, runner, task_name: str) -> str:
    """生图/生视频任务共用骨架：回写 RUNNING → 跑异步任务 → 回写终态。

    用户取消返回 ``cancelled``；其余异常回写 FAILED 后原样重抛，交由 Celery 记录失败。
    """
    sync_task_by_celery_id(self.request.id, TaskStatus.RUNNING)
    try:
        _run_coro(runner(UUID(job_id)))
        sync_task_by_celery_id(self.request.id, TaskStatus.SUCCESS)
        return "ok"
    except GenerativeJobCancelled:
        sync_task_by_celery_id(self.request.id, TaskStatus.CANCELLED, fail_reason="用户取消")
        return "cancelled"
    except Exception as exc:
        sync_task_by_celery_id(self.request.id, TaskStatus.FAILED, fail_reason=str(exc)[:2000])
        logger.exception("%s failed: %s", task_name, job_id)
        raise


@celery_app.task(
    name=TASK_NAMES["run_generative_video_job"],
    bind=True,
    max_retries=0,
)
def run_generative_video_job(self, job_id: str) -> str:
    """Celery 入口：跑异步生视频任务并同步 TaskRecord 状态；用户取消返回 ``cancelled``，异常记日志后重抛。"""
    return _run_generative_task(self, job_id, run_generative_video_job_async, "run_generative_video_job")


@celery_app.task(
    name=TASK_NAMES["run_generative_image_job"],
    bind=True,
    max_retries=0,
)
def run_generative_image_job(self, job_id: str) -> str:
    """Celery 入口：跑异步生图任务并同步 TaskRecord 状态；用户取消返回 ``cancelled``，异常记日志后重抛。"""
    return _run_generative_task(self, job_id, run_generative_image_job_async, "run_generative_image_job")
