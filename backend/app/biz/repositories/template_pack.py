"""服务线模板市场仓储。"""

from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.core.soft_delete import not_deleted
from app.models.biz.template_pack import BizServiceLineTemplatePack
from app.models.biz.template_pack_status import TemplatePackStatus


class ServiceLineTemplatePackRepository(BaseRepository[BizServiceLineTemplatePack]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, BizServiceLineTemplatePack)

    def _catalog_filters(self, viewer_tenant_id: UUID):
        published = BizServiceLineTemplatePack.status == TemplatePackStatus.PUBLISHED.value
        return and_(
            BizServiceLineTemplatePack.is_active.is_(True),
            not_deleted(BizServiceLineTemplatePack),
            published,
            or_(
                BizServiceLineTemplatePack.tenant_id.is_(None),
                BizServiceLineTemplatePack.tenant_id != viewer_tenant_id,
            ),
        )

    async def list_catalog(
        self,
        viewer_tenant_id: UUID,
        *,
        service_line: str | None = None,
        search: str | None = None,
        featured_only: bool = False,
        limit: int = 100,
    ) -> list[BizServiceLineTemplatePack]:
        stmt = (
            select(BizServiceLineTemplatePack)
            .where(self._catalog_filters(viewer_tenant_id))
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

    async def get_catalog_pack(self, pack_id: UUID, viewer_tenant_id: UUID) -> BizServiceLineTemplatePack | None:
        stmt = (
            select(BizServiceLineTemplatePack)
            .where(
                BizServiceLineTemplatePack.id == pack_id,
                self._catalog_filters(viewer_tenant_id),
            )
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_mine(self, tenant_id: UUID) -> list[BizServiceLineTemplatePack]:
        stmt = (
            select(BizServiceLineTemplatePack)
            .where(
                BizServiceLineTemplatePack.tenant_id == tenant_id,
                not_deleted(BizServiceLineTemplatePack),
            )
            .order_by(BizServiceLineTemplatePack.updated_at.desc())
        )
        return list((await self.db.scalars(stmt)).all())

    async def get_mine(self, tenant_id: UUID, pack_id: UUID) -> BizServiceLineTemplatePack | None:
        stmt = (
            select(BizServiceLineTemplatePack)
            .where(
                BizServiceLineTemplatePack.id == pack_id,
                BizServiceLineTemplatePack.tenant_id == tenant_id,
                not_deleted(BizServiceLineTemplatePack),
            )
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_pending_review(self, *, offset: int, limit: int) -> tuple[list[BizServiceLineTemplatePack], int]:
        from sqlalchemy import func

        filters = [
            BizServiceLineTemplatePack.status == TemplatePackStatus.PENDING_REVIEW.value,
            not_deleted(BizServiceLineTemplatePack),
            BizServiceLineTemplatePack.tenant_id.is_not(None),
        ]
        total = await self.db.scalar(select(func.count(BizServiceLineTemplatePack.id)).where(*filters))
        stmt = (
            select(BizServiceLineTemplatePack)
            .where(*filters)
            .order_by(BizServiceLineTemplatePack.submitted_at.asc().nulls_last())
            .offset(offset)
            .limit(limit)
        )
        rows = list((await self.db.scalars(stmt)).all())
        return rows, int(total or 0)

    async def get_for_admin_review(self, pack_id: UUID) -> BizServiceLineTemplatePack | None:
        return await self.get_by_id(pack_id)

    async def get_by_id(self, pack_id: UUID) -> BizServiceLineTemplatePack | None:
        stmt = (
            select(BizServiceLineTemplatePack)
            .where(
                BizServiceLineTemplatePack.id == pack_id,
                not_deleted(BizServiceLineTemplatePack),
            )
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_published_for_admin(self, *, offset: int, limit: int) -> tuple[list[BizServiceLineTemplatePack], int]:
        from sqlalchemy import func

        filters = [
            BizServiceLineTemplatePack.status == TemplatePackStatus.PUBLISHED.value,
            not_deleted(BizServiceLineTemplatePack),
        ]
        total = await self.db.scalar(select(func.count(BizServiceLineTemplatePack.id)).where(*filters))
        stmt = (
            select(BizServiceLineTemplatePack)
            .where(*filters)
            .order_by(
                BizServiceLineTemplatePack.is_active.desc(),
                BizServiceLineTemplatePack.is_featured.desc(),
                BizServiceLineTemplatePack.install_count.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        rows = list((await self.db.scalars(stmt)).all())
        return rows, int(total or 0)
