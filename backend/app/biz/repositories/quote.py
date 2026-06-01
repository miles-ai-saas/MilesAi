"""报价仓储。"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.core.soft_delete import not_deleted
from app.models.biz import BizQuote


class QuoteRepository(BaseRepository[BizQuote]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, BizQuote)

    async def list_by_opportunity(self, tenant_id: UUID, opportunity_id: UUID) -> list[BizQuote]:
        stmt = (
            select(BizQuote)
            .where(
                BizQuote.tenant_id == tenant_id,
                BizQuote.opportunity_id == opportunity_id,
                not_deleted(BizQuote),
            )
            .order_by(BizQuote.created_at.desc())
        )
        return (await self.db.execute(stmt)).scalars().all()
