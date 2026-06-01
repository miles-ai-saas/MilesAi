"""里程碑仓储。"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.core.soft_delete import not_deleted
from app.models.biz import BizMilestone


class MilestoneRepository(BaseRepository[BizMilestone]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, BizMilestone)

    async def list_by_work_package(self, tenant_id: UUID, work_package_id: UUID) -> list[BizMilestone]:
        stmt = (
            select(BizMilestone)
            .where(
                BizMilestone.tenant_id == tenant_id,
                BizMilestone.work_package_id == work_package_id,
                not_deleted(BizMilestone),
            )
            .order_by(BizMilestone.sort_order.asc(), BizMilestone.created_at.asc())
        )
        return (await self.db.execute(stmt)).scalars().all()

    async def list_due_milestones(self, tenant_id: UUID, *, due_before, limit: int = 50) -> list[BizMilestone]:
        """未完成且到期日在 due_before 及之前的里程碑。"""
        stmt = (
            select(BizMilestone)
            .where(
                BizMilestone.tenant_id == tenant_id,
                not_deleted(BizMilestone),
                BizMilestone.completed_at.is_(None),
                BizMilestone.due_date.is_not(None),
                BizMilestone.due_date <= due_before,
            )
            .order_by(BizMilestone.due_date.asc(), BizMilestone.title.asc())
            .limit(limit)
        )
        return (await self.db.execute(stmt)).scalars().all()

    async def list_for_reminder(self, *, due_before, reminder_before_today: str, limit: int = 200) -> list[BizMilestone]:
        """跨租户扫描需发送到期提醒的里程碑（Celery 用）。"""
        stmt = (
            select(BizMilestone)
            .where(
                not_deleted(BizMilestone),
                BizMilestone.completed_at.is_(None),
                BizMilestone.due_date.is_not(None),
                BizMilestone.due_date <= due_before,
            )
            .where(
                (BizMilestone.due_reminder_sent_at.is_(None))
                | (BizMilestone.due_reminder_sent_at < reminder_before_today)
            )
            .order_by(BizMilestone.due_date.asc())
            .limit(limit)
        )
        return (await self.db.execute(stmt)).scalars().all()
