"""项目仓储。"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.core.soft_delete import not_deleted
from app.models.biz import BizProject, BizWorkPackage


class ProjectRepository(BaseRepository[BizProject]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, BizProject)

    async def get_work_packages(self, tenant_id: UUID, project_id: UUID) -> list[BizWorkPackage]:
        stmt = (
            select(BizWorkPackage)
            .where(
                BizWorkPackage.tenant_id == tenant_id,
                BizWorkPackage.project_id == project_id,
                not_deleted(BizWorkPackage),
            )
            .order_by(BizWorkPackage.stage_index.asc(), BizWorkPackage.name.asc())
        )
        return (await self.db.execute(stmt)).scalars().all()

    async def get_work_package(self, wp_id: UUID) -> BizWorkPackage | None:
        wp = await self.db.get(BizWorkPackage, wp_id)
        if wp is None or wp.deleted_at is not None:
            return None
        return wp
