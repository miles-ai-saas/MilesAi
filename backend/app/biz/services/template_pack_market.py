"""服务线模板市场：浏览与一键应用。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.repositories.template_pack import ServiceLineTemplatePackRepository
from app.biz.schemas.service_line_template import BizServiceLineTemplateUpsert
from app.biz.schemas.template_pack import BizServiceLineTemplatePackApplyResult, BizServiceLineTemplatePackOut
from app.biz.services.meta import SERVICE_LINES
from app.biz.services.service_line_template import parse_stage_names
from app.biz.services.service_line_template_admin import ServiceLineTemplateAdminService
from app.biz.services.template_pack_serialize import pack_to_out
from app.common.exceptions import NotFoundError
from app.core.service import BaseService
from app.core.tenant import TenantContext


class ServiceLineTemplatePackMarketService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = ServiceLineTemplatePackRepository(db)
        self._labels = {item.key: item.label for item in SERVICE_LINES}

    async def list_packs(
        self,
        *,
        service_line: str | None = None,
        search: str | None = None,
        featured_only: bool = False,
    ) -> list[BizServiceLineTemplatePackOut]:
        rows = await self.repo.list_catalog(
            self.ctx.tenant_id,
            service_line=service_line,
            search=search,
            featured_only=featured_only,
        )
        return [pack_to_out(r, viewer_tenant_id=self.ctx.tenant_id) for r in rows]

    async def get_pack(self, pack_id: UUID) -> BizServiceLineTemplatePackOut:
        row = await self.repo.get_catalog_pack(pack_id, self.ctx.tenant_id)
        if not row:
            raise NotFoundError("模板包不存在或已下架")
        return pack_to_out(row, viewer_tenant_id=self.ctx.tenant_id)

    async def apply_pack(self, pack_id: UUID) -> BizServiceLineTemplatePackApplyResult:
        row = await self.repo.get_catalog_pack(pack_id, self.ctx.tenant_id)
        if not row:
            raise NotFoundError("模板包不存在或已下架")
        if row.service_line not in self._labels:
            raise NotFoundError("模板包服务线无效")

        stages = parse_stage_names(row.stages)
        ai_config = row.ai_config if isinstance(row.ai_config, dict) else {}
        admin = ServiceLineTemplateAdminService(self.db, self.ctx)
        template = await admin.upsert(
            row.service_line,
            BizServiceLineTemplateUpsert(stages=stages, is_active=True, ai_config=ai_config),
        )
        row.install_count = (row.install_count or 0) + 1
        await self.db.flush()

        return BizServiceLineTemplatePackApplyResult(
            pack_id=str(row.id),
            pack_name=row.name,
            service_line=row.service_line,
            template=template,
        )
