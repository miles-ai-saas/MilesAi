"""运营端服务线模板包审核与运营。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.repositories.template_pack import ServiceLineTemplatePackRepository
from app.biz.schemas.template_pack import BizServiceLineTemplatePackOut
from app.biz.services.template_pack_serialize import pack_to_out
from app.common.exceptions import BadRequestError, NotFoundError
from app.common.schema import PageParams, PageResult
from app.models.biz.template_pack_status import TemplatePackStatus


class AdminTemplatePackReviewService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ServiceLineTemplatePackRepository(db)

    async def list_pending(self, params: PageParams) -> PageResult[BizServiceLineTemplatePackOut]:
        offset = (params.page - 1) * params.size
        rows, total = await self.repo.list_pending_review(offset=offset, limit=params.size)
        return PageResult(
            items=[pack_to_out(r) for r in rows],
            total=total,
            page=params.page,
            size=params.size,
        )

    async def list_published(self, params: PageParams) -> PageResult[BizServiceLineTemplatePackOut]:
        offset = (params.page - 1) * params.size
        rows, total = await self.repo.list_published_for_admin(offset=offset, limit=params.size)
        return PageResult(
            items=[pack_to_out(r) for r in rows],
            total=total,
            page=params.page,
            size=params.size,
        )

    async def get_detail(self, pack_id: UUID) -> BizServiceLineTemplatePackOut:
        row = await self.repo.get_by_id(pack_id)
        if not row:
            raise NotFoundError("模板包不存在")
        return pack_to_out(row)

    async def approve(self, pack_id: UUID, *, admin_id: UUID) -> BizServiceLineTemplatePackOut:
        row = await self._get_pending(pack_id)
        row.status = TemplatePackStatus.PUBLISHED.value
        row.is_active = True
        row.reviewed_at = datetime.now(timezone.utc)
        row.reviewed_by_admin_id = admin_id
        row.review_note = None
        await self.db.flush()
        await self.db.refresh(row)
        return pack_to_out(row)

    async def reject(self, pack_id: UUID, *, admin_id: UUID, note: str | None) -> BizServiceLineTemplatePackOut:
        row = await self._get_pending(pack_id)
        row.status = TemplatePackStatus.REJECTED.value
        row.reviewed_at = datetime.now(timezone.utc)
        row.reviewed_by_admin_id = admin_id
        row.review_note = (note or "").strip() or "不符合上架规范"
        await self.db.flush()
        await self.db.refresh(row)
        return pack_to_out(row)

    async def unpublish(self, pack_id: UUID) -> BizServiceLineTemplatePackOut:
        row = await self._get_published(pack_id)
        row.is_active = False
        row.is_featured = False
        await self.db.flush()
        await self.db.refresh(row)
        return pack_to_out(row)

    async def set_featured(self, pack_id: UUID, *, featured: bool) -> BizServiceLineTemplatePackOut:
        row = await self._get_published(pack_id)
        if not row.is_active:
            raise BadRequestError("已下架模板不可设为精选")
        row.is_featured = featured
        await self.db.flush()
        await self.db.refresh(row)
        return pack_to_out(row)

    async def _get_pending(self, pack_id: UUID):
        row = await self.repo.get_by_id(pack_id)
        if not row:
            raise NotFoundError("模板包不存在")
        if row.status != TemplatePackStatus.PENDING_REVIEW.value:
            raise BadRequestError("模板包不在待审核状态")
        return row

    async def _get_published(self, pack_id: UUID):
        row = await self.repo.get_by_id(pack_id)
        if not row:
            raise NotFoundError("模板包不存在")
        if row.status != TemplatePackStatus.PUBLISHED.value:
            raise BadRequestError("模板包未上架")
        return row
