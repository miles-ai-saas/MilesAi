from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundError
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.app_tenant.prompts.models import PromptTemplate
from app.app_tenant.prompts.schemas.prompt import (
    PromptTemplateCreate,
    PromptTemplateOut,
    PromptTemplateUpdate,
)
from app.common.schema import PageParams, PageResult
from app.core.service import BaseService


class PromptService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def list_templates(self, params: PageParams) -> PageResult[PromptTemplateOut]:
        filters = tenant_filters(self.ctx, PromptTemplate.tenant_id)
        total = await self.db.scalar(
            select(func.count()).select_from(PromptTemplate).where(*filters)
        )
        stmt = (
            select(PromptTemplate)
            .where(*filters)
            .order_by(PromptTemplate.created_at.desc())
            .offset((params.page - 1) * params.size)
            .limit(params.size)
        )
        items = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[PromptTemplateOut.model_validate(i) for i in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def create_template(self, body: PromptTemplateCreate) -> PromptTemplateOut:
        row = PromptTemplate(
            tenant_id=self.ctx.tenant_id,
            name=body.name.strip(),
            description=body.description,
            content=body.content,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return PromptTemplateOut.model_validate(row)

    async def update_template(self, template_id: UUID, body: PromptTemplateUpdate) -> PromptTemplateOut:
        row = await self._get_or_raise(template_id)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(row, k, v)
        await self.db.flush()
        await self.db.refresh(row)
        return PromptTemplateOut.model_validate(row)

    async def delete_template(self, template_id: UUID) -> None:
        row = await self._get_or_raise(template_id)
        await self.db.delete(row)

    async def _get_or_raise(self, template_id: UUID) -> PromptTemplate:
        row = await self.db.get(PromptTemplate, template_id)
        if not row:
            raise NotFoundError("提示词模版不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row
