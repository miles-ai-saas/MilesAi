"""
智能体定时任务 Celery 任务。

Beat 每分钟调用 ``tick_agent_schedules`` 扫描到期任务；
``run_agent_schedule`` 在 Worker 内异步调用 ``AgentService.chat``。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.common.cron import compute_next_run
from app.core.tenant import TenantContext
from app.infra.db import AsyncSessionLocal, get_sync_db
from app.models.agent_schedule import AgentSchedule
from app.models.user import User
from app.core.soft_delete import not_deleted
from app.tenant.agents.schemas.agent import ChatRequest
from app.tenant.agents.services.agent import AgentService
from app.workers.app import celery_app

logger = logging.getLogger(__name__)


async def _run_schedule_async(schedule_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        schedule = await db.get(AgentSchedule, schedule_id)
        if not schedule or schedule.deleted_at is not None or not schedule.enabled:
            return
        if not schedule.created_by:
            logger.warning("schedule %s missing created_by, skip", schedule_id)
            return

        user = await db.get(User, schedule.created_by)
        ctx = TenantContext(
            user_id=schedule.created_by,
            tenant_id=schedule.tenant_id,
            username=user.username if user else "schedule",
            is_superuser=False,
            permissions=frozenset(["agent:read", "agent:write"]),
        )
        svc = AgentService(db, ctx)
        await svc.chat(
            schedule.agent_id,
            ChatRequest(
                query=schedule.content,
                conversation_id=f"schedule:{schedule.id}",
            ),
        )
        schedule.last_run_at = datetime.now(timezone.utc)
        await db.commit()


@celery_app.task(name="app.workers.tasks.agent_schedule.run_agent_schedule")
def run_agent_schedule(schedule_id: str) -> str:
    """执行单条智能体定时任务。"""
    try:
        asyncio.run(_run_schedule_async(UUID(schedule_id)))
        return "ok"
    except Exception:
        logger.exception("run_agent_schedule failed: %s", schedule_id)
        raise


@celery_app.task(name="app.workers.tasks.agent_schedule.tick_agent_schedules")
def tick_agent_schedules() -> str:
    """扫描到期定时任务并派发执行。"""
    now = datetime.now(timezone.utc)
    dispatched = 0
    with get_sync_db() as db:
        stmt = (
            select(AgentSchedule)
            .where(
                not_deleted(AgentSchedule),
                AgentSchedule.enabled.is_(True),
                AgentSchedule.next_run_at.is_not(None),
                AgentSchedule.next_run_at <= now,
            )
            .order_by(AgentSchedule.next_run_at)
            .limit(50)
        )
        schedules = db.execute(stmt).scalars().all()
        for schedule in schedules:
            try:
                schedule.next_run_at = compute_next_run(schedule.cron, now)
                db.flush()
                run_agent_schedule.delay(str(schedule.id))
                dispatched += 1
            except Exception:
                logger.exception("tick failed for schedule %s", schedule.id)
    return f"dispatched={dispatched}"
