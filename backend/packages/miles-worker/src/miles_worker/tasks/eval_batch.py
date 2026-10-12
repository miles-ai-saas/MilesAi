"""Celery：执行 Agent 评测批跑。"""

from __future__ import annotations

from uuid import UUID

from miles_core.infra.db import run_worker_db_coro
from miles_core.jobs.tasks import TASK_NAMES
from miles_core.logging import get_logger
from miles_portal.tenant.eval.services.run_batch import run_eval_batch_async
from miles_worker.app import celery_app

logger = get_logger(__name__)


@celery_app.task(name=TASK_NAMES["run_eval_batch"])
def run_eval_batch(run_id: str) -> str:
    """异步执行评测 run。"""
    try:
        run_worker_db_coro(run_eval_batch_async(UUID(run_id)))
        return "ok"
    except Exception as exc:
        logger.error("run_eval_batch failed: %s: %s", run_id, exc)
        raise
