"""项目业务动态（审计日志聚合）。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.repositories.project import ProjectRepository
from app.biz.schemas.project_activity import BizProjectActivityItem
from app.common.exceptions import NotFoundError
from app.core.service import BaseService
from app.core.tenant import TenantContext, assert_tenant_access
from app.models.platform.user import User
from app.tenant.audit_log.models import TenantAuditLog


_BIZ_ACTION_LABELS: dict[str, str] = {
    "biz.project.create": "创建项目",
    "biz.project.update": "更新项目",
    "biz.project.delete": "删除项目",
    "biz.project.close": "项目结项",
    "biz.project.member.add": "添加成员",
    "biz.project.member.remove": "移除成员",
    "biz.project.archive_case": "案例入库",
    "biz.work_package.create": "创建工作包",
    "biz.work_package.update": "更新工作包",
    "biz.deliverable.create": "添加交付物",
    "biz.deliverable.status_change": "交付物状态变更",
    "biz.deliverable.submit": "提交交付物",
    "biz.deliverable.accept": "验收交付物",
    "biz.deliverable.reject": "驳回交付物",
    "biz.milestone.create": "添加里程碑",
    "biz.milestone.due_reminder": "里程碑提醒",
}


class ProjectActivityService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.project_repo = ProjectRepository(db)

    async def list_activity(self, project_id: UUID, *, limit: int = 30) -> list[BizProjectActivityItem]:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError("项目不存在")
        assert_tenant_access(self.ctx, project.tenant_id)

        pid = str(project_id)
        stmt = (
            select(TenantAuditLog)
            .where(
                TenantAuditLog.tenant_id == self.ctx.tenant_id,
                TenantAuditLog.action.like("biz.%"),
                or_(
                    and_(TenantAuditLog.resource_type == "biz_project", TenantAuditLog.resource_id == pid),
                    TenantAuditLog.detail["project_id"].astext == pid,
                ),
            )
            .order_by(TenantAuditLog.created_at.desc())
            .limit(limit)
        )
        rows = (await self.db.scalars(stmt)).all()
        user_ids = {r.user_id for r in rows if r.user_id}
        usernames: dict[UUID, str] = {}
        if user_ids:
            result = await self.db.execute(select(User.id, User.username).where(User.id.in_(user_ids)))
            usernames = {uid: name for uid, name in result.all()}

        items: list[BizProjectActivityItem] = []
        for row in rows:
            items.append(BizProjectActivityItem(
                id=str(row.id),
                action=row.action,
                label=_BIZ_ACTION_LABELS.get(row.action, row.action),
                username=usernames.get(row.user_id) if row.user_id else None,
                created_at=row.created_at.isoformat() if row.created_at else "",
                detail=row.detail if isinstance(row.detail, dict) else {},
            ))
        return items
