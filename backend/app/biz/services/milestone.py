"""工作包里程碑 CRUD。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.audit import log_biz_action
from app.biz.repositories.milestone import MilestoneRepository
from app.biz.repositories.project import ProjectRepository
from app.biz.schemas.milestone import BizMilestoneCreate, BizMilestoneOut, BizMilestoneUpdate
from app.common.exceptions import NotFoundError
from app.core.service import BaseService
from app.core.soft_delete import mark_deleted
from app.core.tenant import TenantContext, assert_tenant_access
from app.models.biz import BizMilestone


class MilestoneService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = MilestoneRepository(db)
        self.project_repo = ProjectRepository(db)

    async def list_milestones(self, project_id: UUID, wp_id: UUID) -> list[BizMilestoneOut]:
        await self._ensure_work_package(project_id, wp_id)
        rows = await self.repo.list_by_work_package(self.ctx.tenant_id, wp_id)
        return [self._to_out(r) for r in rows]

    async def create(self, project_id: UUID, wp_id: UUID, body: BizMilestoneCreate) -> BizMilestoneOut:
        await self._ensure_work_package(project_id, wp_id)
        row = BizMilestone(
            tenant_id=self.ctx.tenant_id,
            project_id=project_id,
            work_package_id=wp_id,
            title=body.title.strip(),
            due_date=body.due_date,
            sort_order=body.sort_order,
        )
        self.db.add(row)
        await self.db.flush()
        await log_biz_action(
            self.db, self.ctx,
            action="biz.milestone.create",
            resource_type="biz_milestone",
            resource_id=row.id,
            detail={"project_id": str(project_id), "work_package_id": str(wp_id), "title": row.title},
        )
        return self._to_out(row)

    async def update(self, project_id: UUID, wp_id: UUID, milestone_id: UUID, body: BizMilestoneUpdate) -> BizMilestoneOut:
        row = await self._get_or_raise(project_id, wp_id, milestone_id)
        for f in ("title", "due_date", "completed_at", "sort_order"):
            val = getattr(body, f, None)
            if val is not None:
                setattr(row, f, val.strip() if isinstance(val, str) and f == "title" else val)
        await self.db.flush()
        return self._to_out(row)

    async def delete(self, project_id: UUID, wp_id: UUID, milestone_id: UUID) -> None:
        row = await self._get_or_raise(project_id, wp_id, milestone_id)
        await mark_deleted(self.db, row)

    async def _ensure_work_package(self, project_id: UUID, wp_id: UUID) -> None:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError("项目不存在")
        assert_tenant_access(self.ctx, project.tenant_id)
        wp = await self.project_repo.get_work_package(wp_id)
        if not wp or wp.project_id != project_id:
            raise NotFoundError("工作包不存在")

    async def _get_or_raise(self, project_id: UUID, wp_id: UUID, milestone_id: UUID) -> BizMilestone:
        await self._ensure_work_package(project_id, wp_id)
        row = await self.repo.get_by_id(milestone_id)
        if not row or row.work_package_id != wp_id:
            raise NotFoundError("里程碑不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row

    def _to_out(self, r: BizMilestone) -> BizMilestoneOut:
        due = r.due_date.isoformat() if hasattr(r.due_date, "isoformat") and r.due_date else r.due_date
        return BizMilestoneOut(
            id=r.id,
            project_id=r.project_id,
            work_package_id=r.work_package_id,
            title=r.title,
            due_date=due,
            completed_at=r.completed_at,
            sort_order=r.sort_order,
        )
