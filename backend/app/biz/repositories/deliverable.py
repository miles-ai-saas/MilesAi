"""交付物仓储。"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.core.soft_delete import not_deleted
from app.models.biz import BizDeliverable


class DeliverableRepository(BaseRepository[BizDeliverable]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, BizDeliverable)

    async def list_by_project(self, tenant_id: UUID, project_id: UUID) -> list[BizDeliverable]:
        stmt = (
            select(BizDeliverable)
            .where(
                BizDeliverable.tenant_id == tenant_id,
                BizDeliverable.project_id == project_id,
                not_deleted(BizDeliverable),
            )
            .order_by(BizDeliverable.submitted_at.desc().nulls_last(), BizDeliverable.name.asc())
        )
        return (await self.db.execute(stmt)).scalars().all()
