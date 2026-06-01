"""里程碑到期查询与提醒。"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.audit import log_biz_action
from app.biz.repositories.milestone import MilestoneRepository
from app.biz.repositories.project import ProjectRepository
from app.biz.schemas.milestone import BizMilestoneDueOut
from app.core.service import BaseService
from app.core.tenant import TenantContext
from app.models.biz import BizMilestone


class MilestoneDueService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = MilestoneRepository(db)
        self.project_repo = ProjectRepository(db)

    async def list_due(self, *, days: int = 7, limit: int = 50) -> list[BizMilestoneDueOut]:
        due_before = date.today() + timedelta(days=max(days, 0))
        rows = await self.repo.list_due_milestones(self.ctx.tenant_id, due_before=due_before, limit=limit)
        return [await self._to_due_out(r) for r in rows]

    async def send_due_reminders(self, *, lookahead_days: int = 3) -> int:
        """为当前租户发送里程碑到期提醒（审计留痕），返回处理条数。"""
        today = date.today()
        due_before = today + timedelta(days=lookahead_days)
        today_str = today.isoformat()
        rows = await self.repo.list_due_milestones(self.ctx.tenant_id, due_before=due_before, limit=200)
        sent = 0
        for row in rows:
            if row.due_reminder_sent_at == today_str:
                continue
            await log_biz_action(
                self.db, self.ctx,
                action="biz.milestone.due_reminder",
                resource_type="biz_milestone",
                resource_id=row.id,
                detail={
                    "project_id": str(row.project_id),
                    "work_package_id": str(row.work_package_id),
                    "title": row.title,
                    "due_date": str(row.due_date),
                },
            )
            row.due_reminder_sent_at = today_str
            sent += 1
        if sent:
            await self.db.flush()
        return sent

    async def _to_due_out(self, row: BizMilestone) -> BizMilestoneDueOut:
        wp = await self.project_repo.get_work_package(row.work_package_id)
        project = await self.project_repo.get_by_id(row.project_id)
        due = row.due_date
        overdue = bool(due and due < date.today())
        return BizMilestoneDueOut(
            id=row.id,
            project_id=row.project_id,
            project_name=project.name if project else "",
            work_package_id=row.work_package_id,
            work_package_name=wp.name if wp else "",
            title=row.title,
            due_date=str(due) if due else None,
            overdue=overdue,
        )
