"""服务线模板市场仓储。"""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.core.soft_delete import not_deleted
from app.models.biz.template_pack import BizServiceLineTemplatePack


class ServiceLineTemplatePackRepository(BaseRepository[BizServiceLineTemplatePack]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, BizServiceLineTemplatePack)

    async def list_catalog(
        self,
        *,
        service_line: str | None = None,
        search: str | None = None,
        featured_only: bool = False,
        limit: int = 100,
    ) -> list[BizServiceLineTemplatePack]:
        stmt = (
            select(BizServiceLineTemplatePack)
            .where(
                BizServiceLineTemplatePack.tenant_id.is_(None),
                BizServiceLineTemplatePack.is_active.is_(True),
                not_deleted(BizServiceLineTemplatePack),
            )
            .order_by(
                BizServiceLineTemplatePack.is_featured.desc(),
                BizServiceLineTemplatePack.sort_order.asc(),
                BizServiceLineTemplatePack.install_count.desc(),
            )
            .limit(limit)
        )
        if service_line:
            stmt = stmt.where(BizServiceLineTemplatePack.service_line == service_line)
        if featured_only:
            stmt = stmt.where(BizServiceLineTemplatePack.is_featured.is_(True))
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    BizServiceLineTemplatePack.name.ilike(pattern),
                    BizServiceLineTemplatePack.description.ilike(pattern),
                )
            )
        return list((await self.db.scalars(stmt)).all())

    async def get_catalog_pack(self, pack_id: UUID) -> BizServiceLineTemplatePack | None:
        stmt = (
            select(BizServiceLineTemplatePack)
            .where(
                BizServiceLineTemplatePack.id == pack_id,
                BizServiceLineTemplatePack.tenant_id.is_(None),
                BizServiceLineTemplatePack.is_active.is_(True),
                not_deleted(BizServiceLineTemplatePack),
            )
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
