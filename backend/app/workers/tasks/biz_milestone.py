"""业务中心 Celery 任务：里程碑到期提醒。"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

from sqlalchemy import select

from app.core.logging import get_logger
from app.core.tenant import TenantContext
from app.infra.db import AsyncSessionLocal
from app.biz.services.milestone_due import MilestoneDueService
from app.models.platform.user import User
from app.workers.app import celery_app

logger = get_logger(__name__)


async def _tenant_ctx(db, tenant_id) -> TenantContext | None:
    user = await db.scalar(
        select(User).where(User.tenant_id == tenant_id).order_by(User.is_superuser.desc()).limit(1)
    )
    if not user:
        return None
    return TenantContext(
        user_id=user.id,
        tenant_id=tenant_id,
        username=user.username,
        is_superuser=user.is_superuser,
        permissions=frozenset(["biz:project:read", "biz:project:write"]),
    )


async def _check_milestone_due_async() -> int:
    async with AsyncSessionLocal() as db:
        from app.models.biz import BizMilestone
        from app.core.soft_delete import not_deleted

        today = date.today()
        due_before = today + timedelta(days=3)
        tenant_ids = (
            await db.scalars(
                select(BizMilestone.tenant_id)
                .where(
                    not_deleted(BizMilestone),
                    BizMilestone.completed_at.is_(None),
                    BizMilestone.due_date.is_not(None),
                    BizMilestone.due_date <= due_before,
                )
                .distinct()
            )
        ).all()

        total = 0
        for tenant_id in tenant_ids:
            ctx = await _tenant_ctx(db, tenant_id)
            if not ctx:
                continue
            try:
                sent = await MilestoneDueService(db, ctx).send_due_reminders(lookahead_days=3)
                total += sent
                await db.commit()
            except Exception:
                await db.rollback()
                logger.exception("milestone due reminder failed for tenant %s", tenant_id)
        return total


@celery_app.task(name="app.workers.tasks.biz_milestone.check_milestone_due")
def check_milestone_due() -> str:
    """扫描各租户即将到期里程碑并写入审计提醒。"""
    try:
        count = asyncio.run(_check_milestone_due_async())
        return f"reminders={count}"
    except Exception:
        logger.exception("check_milestone_due failed")
        raise
