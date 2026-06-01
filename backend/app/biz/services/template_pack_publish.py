"""租户发布服务线模板包。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.repositories.service_line_template import ServiceLineTemplateRepository
from app.biz.repositories.template_pack import ServiceLineTemplatePackRepository
from app.biz.schemas.template_pack import (
    BizServiceLineTemplatePackCreate,
    BizServiceLineTemplatePackOut,
    BizServiceLineTemplatePackUpdate,
)
from app.biz.services.meta import SERVICE_LINES
from app.biz.services.service_line_template import parse_stage_names
from app.biz.services.service_line_template_admin import ServiceLineTemplateAdminService
from app.biz.services.template_pack_meta import (
    default_category_for_service_line,
    normalize_customer_type_tags,
    validate_category,
)
from app.biz.services.template_pack_serialize import pack_to_out
from app.common.exceptions import BadRequestError, NotFoundError
from app.core.service import BaseService
from app.core.soft_delete import mark_deleted
from app.core.tenant import TenantContext
from app.models.biz.template_pack import BizServiceLineTemplatePack
from app.models.biz.template_pack_status import TemplatePackStatus
from app.models.platform.tenant import Tenant


class ServiceLineTemplatePackPublishService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = ServiceLineTemplatePackRepository(db)
        self.template_repo = ServiceLineTemplateRepository(db)

    async def list_mine(self) -> list[BizServiceLineTemplatePackOut]:
        rows = await self.repo.list_mine(self.ctx.tenant_id)
        return [pack_to_out(r, viewer_tenant_id=self.ctx.tenant_id) for r in rows]

    async def create_from_template(self, body: BizServiceLineTemplatePackCreate) -> BizServiceLineTemplatePackOut:
        if body.service_line not in {s.key for s in SERVICE_LINES}:
            raise NotFoundError("未知服务线")
        name = (body.name or "").strip()
        if not name:
            raise BadRequestError("请填写模板名称")

        admin = ServiceLineTemplateAdminService(self.db, self.ctx)
        templates = await admin.list_templates()
        current = next((t for t in templates if t.service_line == body.service_line), None)
        if not current or not current.stages:
            raise BadRequestError("当前服务线尚无阶段配置，请先编辑服务线模板")

        tenant = await self.db.scalar(select(Tenant).where(Tenant.id == self.ctx.tenant_id))
        publisher_name = tenant.name if tenant else self.ctx.username

        row = BizServiceLineTemplatePack(
            tenant_id=self.ctx.tenant_id,
            category=validate_category(body.category or default_category_for_service_line(body.service_line)),
            service_line=body.service_line,
            name=name,
            description=(body.description or "").strip() or None,
            stages=list(current.stages),
            ai_config=dict(current.ai_config or {}),
            publisher_name=publisher_name,
            publisher_type="tenant",
            tags=normalize_customer_type_tags(body.tags),
            is_featured=False,
            install_count=0,
            is_active=True,
            status=TemplatePackStatus.DRAFT.value,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return pack_to_out(row, viewer_tenant_id=self.ctx.tenant_id)

    async def update_mine(self, pack_id: UUID, body: BizServiceLineTemplatePackUpdate) -> BizServiceLineTemplatePackOut:
        row = await self._get_editable(pack_id)
        if body.name is not None:
            name = body.name.strip()
            if not name:
                raise BadRequestError("名称不能为空")
            row.name = name
        if body.description is not None:
            row.description = body.description.strip() or None
        if body.category is not None:
            row.category = validate_category(body.category)
        if body.tags is not None:
            row.tags = normalize_customer_type_tags(body.tags)
        if body.stages is not None:
            stages = [s.strip() for s in body.stages if s.strip()]
            if not stages:
                raise BadRequestError("至少保留一个阶段")
            row.stages = stages
        if body.ai_config is not None:
            row.ai_config = body.ai_config
        await self.db.flush()
        await self.db.refresh(row)
        return pack_to_out(row, viewer_tenant_id=self.ctx.tenant_id)

    async def unpublish_mine(self, pack_id: UUID) -> BizServiceLineTemplatePackOut:
        row = await self.repo.get_mine(self.ctx.tenant_id, pack_id)
        if not row:
            raise NotFoundError("模板包不存在")
        if row.status != TemplatePackStatus.PUBLISHED.value:
            raise BadRequestError("仅已上架模板可主动下架")
        row.status = TemplatePackStatus.DRAFT.value
        row.is_active = False
        row.is_featured = False
        await self.db.flush()
        await self.db.refresh(row)
        return pack_to_out(row, viewer_tenant_id=self.ctx.tenant_id)

    async def submit(self, pack_id: UUID) -> BizServiceLineTemplatePackOut:
        row = await self._get_editable(pack_id)
        if not parse_stage_names(row.stages):
            raise BadRequestError("模板阶段不能为空")
        row.status = TemplatePackStatus.PENDING_REVIEW.value
        row.submitted_at = datetime.now(timezone.utc)
        row.review_note = None
        row.reviewed_at = None
        row.reviewed_by_admin_id = None
        await self.db.flush()
        await self.db.refresh(row)
        return pack_to_out(row, viewer_tenant_id=self.ctx.tenant_id)

    async def withdraw(self, pack_id: UUID) -> None:
        row = await self.repo.get_mine(self.ctx.tenant_id, pack_id)
        if not row:
            raise NotFoundError("模板包不存在")
        if row.status == TemplatePackStatus.PUBLISHED.value:
            raise BadRequestError("已上架模板请先下架再删除")
        mark_deleted(row)
        await self.db.flush()

    async def _get_editable(self, pack_id: UUID) -> BizServiceLineTemplatePack:
        row = await self.repo.get_mine(self.ctx.tenant_id, pack_id)
        if not row:
            raise NotFoundError("模板包不存在")
        if row.status not in (TemplatePackStatus.DRAFT.value, TemplatePackStatus.REJECTED.value):
            raise BadRequestError("仅草稿或已驳回状态可编辑")
        return row
