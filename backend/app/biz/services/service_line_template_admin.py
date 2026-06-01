"""服务线模板管理（租户级覆盖）。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.repositories.service_line_template import ServiceLineTemplateRepository
from app.biz.schemas.service_line_template import BizServiceLineTemplateOut, BizServiceLineTemplateUpsert
from app.biz.services.meta import SERVICE_LINES
from app.biz.services.service_line_template import parse_stage_names
from app.common.exceptions import BadRequestError, NotFoundError
from app.core.service import BaseService
from app.core.soft_delete import mark_deleted
from app.core.tenant import TenantContext
from app.models.biz import BizServiceLineTemplate


class ServiceLineTemplateAdminService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = ServiceLineTemplateRepository(db)

    async def list_templates(self) -> list[BizServiceLineTemplateOut]:
        labels = {item.key: item.label for item in SERVICE_LINES}
        out: list[BizServiceLineTemplateOut] = []
        for item in SERVICE_LINES:
            tenant_row = await self.repo.get_tenant_template(self.ctx.tenant_id, item.key)
            if tenant_row:
                out.append(self._to_out(tenant_row, labels.get(item.key, item.key), source="tenant", editable=True))
                continue
            global_row = await self._get_global_template(item.key)
            if global_row:
                out.append(self._to_out(global_row, labels.get(item.key, item.key), source="global", editable=True))
            else:
                out.append(BizServiceLineTemplateOut(
                    service_line=item.key,
                    label=labels.get(item.key, item.key),
                    stages=[],
                    source="none",
                    is_active=True,
                    is_editable=True,
                ))
        return out

    async def upsert(self, service_line: str, body: BizServiceLineTemplateUpsert) -> BizServiceLineTemplateOut:
        if service_line not in {s.key for s in SERVICE_LINES}:
            raise NotFoundError("未知服务线")
        stages = [s.strip() for s in body.stages if s.strip()]
        if not stages:
            raise BadRequestError("至少保留一个阶段")
        row = await self.repo.get_tenant_template(self.ctx.tenant_id, service_line)
        if row:
            row.stages = stages
            row.is_active = body.is_active
            if body.ai_config is not None:
                row.ai_config = body.ai_config
        else:
            global_row = await self._get_global_template(service_line)
            base_ai = global_row.ai_config if global_row and isinstance(global_row.ai_config, dict) else {}
            row = BizServiceLineTemplate(
                tenant_id=self.ctx.tenant_id,
                service_line=service_line,
                stages=stages,
                is_active=body.is_active,
                ai_config=body.ai_config if body.ai_config is not None else base_ai,
            )
            self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        labels = {item.key: item.label for item in SERVICE_LINES}
        return self._to_out(row, labels.get(service_line, service_line), source="tenant", editable=True)

    async def reset(self, service_line: str) -> BizServiceLineTemplateOut:
        row = await self.repo.get_tenant_template(self.ctx.tenant_id, service_line)
        if row:
            mark_deleted(row)
            await self.db.flush()
        labels = {item.key: item.label for item in SERVICE_LINES}
        global_row = await self._get_global_template(service_line)
        if global_row:
            return self._to_out(global_row, labels.get(service_line, service_line), source="global", editable=True)
        return BizServiceLineTemplateOut(
            service_line=service_line,
            label=labels.get(service_line, service_line),
            stages=[],
            source="none",
            is_active=True,
            is_editable=True,
        )

    async def _get_global_template(self, service_line: str) -> BizServiceLineTemplate | None:
        from sqlalchemy import select

        stmt = (
            select(BizServiceLineTemplate)
            .where(
                BizServiceLineTemplate.service_line == service_line,
                BizServiceLineTemplate.tenant_id.is_(None),
                BizServiceLineTemplate.deleted_at.is_(None),
            )
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    def _to_out(row: BizServiceLineTemplate, label: str, *, source: str, editable: bool) -> BizServiceLineTemplateOut:
        return BizServiceLineTemplateOut(
            service_line=row.service_line,
            label=label,
            stages=parse_stage_names(row.stages),
            source=source,
            template_id=str(row.id),
            is_active=row.is_active,
            is_editable=editable,
            ai_config=row.ai_config if isinstance(row.ai_config, dict) else {},
        )
