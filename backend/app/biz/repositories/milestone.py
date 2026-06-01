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
