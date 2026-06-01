"""仪表盘统计服务。

从多表实时聚合：客户数、在制项目、待验收交付物、
进行中工作包、最近更新项目。
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.schemas.dashboard import DashboardSummaryOut, RecentProjectItem
from app.core.service import BaseService
from app.core.soft_delete import not_deleted
from app.core.tenant import TenantContext, tenant_filters
from app.models.biz import BizClient, BizDeliverable, BizProject, BizWorkPackage


class DashboardService(BaseService):
    """实时统计仪表盘——无缓存，每次请求从各表聚合。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def get_summary(self) -> DashboardSummaryOut:
        """返回租户级业务总览：客户/项目/工作包/交付物四维统计。"""
        return DashboardSummaryOut(
            total_clients=await self._count(BizClient),
            active_projects=await self._count_active_projects(),
            pending_deliverables=await self._count(BizDeliverable, BizDeliverable.status == "submitted"),
            work_packages_in_progress=await self._count(BizWorkPackage, BizWorkPackage.status == "in_progress"),
            recent_projects=await self._recent_projects(),
        )

    async def _count(self, model, *filters) -> int:
        """通用计数：在租户范围 + 未删除的记录中计数。"""
        conds = tenant_filters(self.ctx, model.tenant_id) + [not_deleted(model)] + list(filters)
        stmt = select(func.count()).where(*conds)
        return await self.db.scalar(stmt) or 0

    async def _count_active_projects(self) -> int:
        """在制项目数 = 草稿 + 进行中 + 暂停。"""
        return await self._count(BizProject, BizProject.status.in_(["draft", "active", "on_hold"]))

    async def _recent_projects(self, limit: int = 5) -> list[RecentProjectItem]:
        """最近更新的项目（带客户名称），按 updated_at 降序取前 N 条。"""
        stmt = (
            select(BizProject, BizClient.name.label("client_name"))
            .join(BizClient, BizClient.id == BizProject.client_id, isouter=True)
            .where(
                BizProject.tenant_id == self.ctx.tenant_id,
                not_deleted(BizProject),
            )
            .order_by(BizProject.updated_at.desc())
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).all()
        return [RecentProjectItem(id=str(r.BizProject.id), name=r.BizProject.name, status=r.BizProject.status, client_name=r.client_name or "-") for r in rows]
