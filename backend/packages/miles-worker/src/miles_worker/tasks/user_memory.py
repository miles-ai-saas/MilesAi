"""Celery：抽取/更新跨会话用户记忆。"""

from __future__ import annotations

from miles_core.infra.db import run_worker_db_coro
from miles_core.jobs.tasks import TASK_NAMES
from miles_core.logging import get_logger
from miles_portal.tenant.agents.services.user_memory_extract import extract_user_memory_async
from miles_worker.app import celery_app

logger = get_logger(__name__)


@celery_app.task(name=TASK_NAMES["run_user_memory_extract"])
def run_user_memory_extract(
    tenant_id: str,
    user_id: str,
    agent_id: str,
    user_text: str,
    assistant_text: str,
    trace_id: str | None = None,
) -> str:
    """异步更新 (tenant, user, agent) 长期记忆。"""
    try:
        return run_worker_db_coro(
            extract_user_memory_async(
                tenant_id=tenant_id,
                user_id=user_id,
                agent_id=agent_id,
                user_text=user_text,
                assistant_text=assistant_text,
                trace_id=trace_id,
            )
        )
    except Exception as exc:
        logger.error("run_user_memory_extract failed: %s/%s: %s", agent_id, user_id, exc)
        raise
