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
from app.common.exceptions import NotFoundError
from app.core.service import BaseService
from app.core.tenant import TenantContext
from app.models.biz.template_pack import BizServiceLineTemplatePack


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
            service_line=service_line,
            search=search,
            featured_only=featured_only,
        )
        return [self._to_out(row) for row in rows]

    async def get_pack(self, pack_id: UUID) -> BizServiceLineTemplatePackOut:
        row = await self.repo.get_catalog_pack(pack_id)
        if not row:
            raise NotFoundError("模板包不存在或已下架")
        return self._to_out(row)

    async def apply_pack(self, pack_id: UUID) -> BizServiceLineTemplatePackApplyResult:
        row = await self.repo.get_catalog_pack(pack_id)
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

    def _to_out(self, row: BizServiceLineTemplatePack) -> BizServiceLineTemplatePackOut:
        tags = row.tags if isinstance(row.tags, list) else []
        return BizServiceLineTemplatePackOut(
            id=str(row.id),
            service_line=row.service_line,
            service_line_label=self._labels.get(row.service_line, row.service_line),
            name=row.name,
            description=row.description,
            stages=parse_stage_names(row.stages),
            ai_config=row.ai_config if isinstance(row.ai_config, dict) else {},
            publisher_name=row.publisher_name,
            publisher_type=row.publisher_type,
            tags=[str(t) for t in tags],
            is_featured=row.is_featured,
            install_count=row.install_count or 0,
        )
