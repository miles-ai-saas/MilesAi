"""提示词模板 CRUD（智能体 system_prompt 等可引用）。

与 Agent.config 内联 prompt 并存；工作台按 prompt:read 统计数量。
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundError
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.models.category import CategoryDomain
from app.models.tag import TagEntityType
from app.tenant.categories.services.category import CategoryService
from app.tenant.tags.schemas.tag import TagRefOut
from app.tenant.tags.services.tag import TagService
from app.tenant.prompts.models import PromptTemplate
from app.tenant.prompts.meta import prompts_meta_dict
from app.tenant.prompts.schemas.meta import PromptMetaOut
from app.tenant.prompts.schemas.prompt import (
    PromptTemplateCreate,
    PromptTemplateOut,
    PromptTemplateUpdate,
)
from app.common.schema import PageParams, PageResult
from app.core.soft_delete import append_not_deleted, is_marked_deleted, mark_deleted
from app.core.service import BaseService


class PromptService(BaseService):
    """租户级 PromptTemplate 管理。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def get_meta(self) -> PromptMetaOut:
        """返回枚举展示字典（无 DB 查询，文案来自 tenant/*/meta.py）。"""
        return PromptMetaOut.model_validate(prompts_meta_dict())

    async def list_templates(
        self,
        params: PageParams,
        *,
        category_id: UUID | None = None,
        tag_ids: list[UUID] | None = None,
    ) -> PageResult[PromptTemplateOut]:
        """分页列表（tenant_filters）；可按 category_id 筛选。"""
        filters = append_not_deleted(
            tenant_filters(self.ctx, PromptTemplate.tenant_id),
            PromptTemplate,
        )
        if category_id is not None:
            filters.append(PromptTemplate.category_id == category_id)
        tag_subq = TagService(self.db, self.ctx).entity_id_filter(TagEntityType.PROMPT, tag_ids or [])
        if tag_subq is not None:
            filters.append(PromptTemplate.id.in_(tag_subq))
        total = await self.db.scalar(select(func.count()).select_from(PromptTemplate).where(*filters))
        stmt = select(PromptTemplate).where(*filters).order_by(PromptTemplate.created_at.desc()).offset((params.page - 1) * params.size).limit(params.size)
        items = (await self.db.execute(stmt)).scalars().all()
        cat_ids = {i.category_id for i in items if i.category_id}
        cat_names = await CategoryService(self.db, self.ctx).get_category_name_map(CategoryDomain.PROMPT, cat_ids)
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.PROMPT, {i.id for i in items})
        return PageResult(
            items=[self._to_out(i, cat_names, tags_map.get(i.id, [])) for i in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    def _to_out(
        self,
        row: PromptTemplate,
        cat_names: dict[UUID, str],
        tags: list[TagRefOut] | None = None,
    ) -> PromptTemplateOut:
        return PromptTemplateOut(
            id=row.id,
            tenant_id=row.tenant_id,
            category_id=row.category_id,
            category_name=cat_names.get(row.category_id) if row.category_id else None,
            tags=tags or [],
            name=row.name,
            description=row.description,
            content=row.content,
            is_active=row.is_active,
            created_at=row.created_at,
        )

    async def create_template(self, body: PromptTemplateCreate) -> PromptTemplateOut:
        await CategoryService(self.db, self.ctx).validate_category_for_domain(body.category_id, CategoryDomain.PROMPT)
        row = PromptTemplate(
            tenant_id=self.ctx.tenant_id,
            category_id=body.category_id,
            name=body.name.strip(),
            description=body.description,
            content=body.content,
        )
        self.db.add(row)
        await self.db.flush()
        if body.tag_ids:
            await TagService(self.db, self.ctx).replace_entity_tags(TagEntityType.PROMPT, row.id, body.tag_ids)
        await self.db.refresh(row)
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.PROMPT, {row.id})
        return self._to_out(row, {}, tags_map.get(row.id, []))

    async def update_template(self, template_id: UUID, body: PromptTemplateUpdate) -> PromptTemplateOut:
        row = await self._get_or_raise(template_id)
        data = body.model_dump(exclude_unset=True)
        tag_ids = data.pop("tag_ids", None)
        if "category_id" in data:
            await CategoryService(self.db, self.ctx).validate_category_for_domain(data.get("category_id"), CategoryDomain.PROMPT)
        for k, v in data.items():
            setattr(row, k, v)
        await self.db.flush()
        if tag_ids is not None:
            await TagService(self.db, self.ctx).replace_entity_tags(TagEntityType.PROMPT, row.id, tag_ids)
        await self.db.refresh(row)
        cat_names = await CategoryService(self.db, self.ctx).get_category_name_map(
            CategoryDomain.PROMPT,
            {row.category_id} if row.category_id else set(),
        )
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.PROMPT, {row.id})
        return self._to_out(row, cat_names, tags_map.get(row.id, []))

    async def delete_template(self, template_id: UUID) -> None:
        row = await self._get_or_raise(template_id)
        await TagService(self.db, self.ctx).clear_entity_tags(TagEntityType.PROMPT, row.id)
        await mark_deleted(self.db, row)

    async def _get_or_raise(self, template_id: UUID) -> PromptTemplate:
        """校验存在、未删、租户归属。"""
        row = await self.db.get(PromptTemplate, template_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("提示词模版不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row
