"""流程 CRUD、模板与序列化。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_ai.flow_runtime.templates.registry import list_flow_templates
from miles_common.exceptions import NotFoundError
from miles_common.schema import PageParams, PageResult
from miles_core.models.flow import Flow, FlowStatus
from miles_core.models.meta.tag import TagEntityType
from miles_core.service import BaseService
from miles_core.soft_delete import is_marked_deleted, mark_deleted
from miles_core.tenant import TenantContext, assert_tenant_access, tenant_filters
from miles_portal.deletion.cascade import before_delete_flow
from miles_portal.tenant.flows.meta import flow_meta_dict
from miles_portal.tenant.flows.repositories.flow import FlowRepository, FlowVersionRepository
from miles_portal.tenant.flows.schemas.flow import FlowCreate, FlowOut, FlowUpdate
from miles_portal.tenant.flows.schemas.meta import FlowMetaOut
from miles_portal.tenant.flows.schemas.template import FlowTemplateOut, FlowTemplatesOut
from miles_portal.tenant.tags.schemas.tag import TagRefOut
from miles_portal.tenant.tags.services.tag import TagService


class FlowCrudMixin(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = FlowRepository(db)
        self.version_repo = FlowVersionRepository(db)

    async def get_meta(self) -> FlowMetaOut:
        """返回枚举展示字典（无 DB 查询，文案来自 tenant/*/meta.py）。"""
        return FlowMetaOut.model_validate(flow_meta_dict())

    async def list_templates(self) -> FlowTemplatesOut:
        """返回内置画布模板（含 graph_json，无 DB 查询）。"""
        items = [FlowTemplateOut.model_validate(row) for row in list_flow_templates()]
        return FlowTemplatesOut(items=items)

    async def _get_flow_or_raise(self, flow_id: UUID) -> Flow:
        flow = await self.repo.get_by_id(flow_id)
        if not flow or is_marked_deleted(flow):
            raise NotFoundError("流程不存在")
        assert_tenant_access(self.ctx, flow.tenant_id)
        return flow

    def _to_out(self, row: Flow, tags: list[TagRefOut] | None = None) -> FlowOut:
        return FlowOut(
            id=row.id,
            tenant_id=row.tenant_id,
            name=row.name,
            description=row.description,
            tags=tags or [],
            status=row.status,
            current_version=row.current_version,
            created_at=row.created_at,
        )

    async def list_flows(
        self,
        params: PageParams,
        *,
        tag_ids: list[UUID] | None = None,
    ) -> PageResult[FlowOut]:
        """分页列出流程，可按标签筛选，并批量补全标签引用。"""
        filters = tenant_filters(self.ctx, Flow.tenant_id)
        tag_subq = TagService(self.db, self.ctx).entity_id_filter(TagEntityType.FLOW, tag_ids or [])
        if tag_subq is not None:
            filters.append(Flow.id.in_(tag_subq))
        page = await self.repo.list_page(
            page=params.page,
            size=params.size,
            filters=filters,
            order_by=Flow.created_at.desc(),
        )
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.FLOW, {f.id for f in page.items})
        return PageResult(
            items=[self._to_out(f, tags_map.get(f.id, [])) for f in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def create_flow(self, body: FlowCreate) -> FlowOut:
        """创建流程并写入初始版本；受租户流程数配额约束。"""
        from miles_portal.tenant.system.services.quota import assert_can_create_flow

        await assert_can_create_flow(self.db, self.ctx.tenant_id)
        flow = await self.repo.create(
            tenant_id=self.ctx.tenant_id,
            name=body.name,
            description=body.description,
            status=FlowStatus.DRAFT,
            current_version=0,
        )
        await self.db.flush()
        if body.tag_ids:
            await TagService(self.db, self.ctx).replace_entity_tags(TagEntityType.FLOW, flow.id, body.tag_ids)
        await self._save_version(flow, body.graph_json, remark="初始版本")
        await self.db.refresh(flow)
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.FLOW, {flow.id})
        return self._to_out(flow, tags_map.get(flow.id, []))

    async def get_flow(self, flow_id: UUID) -> FlowOut:
        """返回流程详情并附标签。"""
        flow = await self._get_flow_or_raise(flow_id)
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.FLOW, {flow.id})
        return self._to_out(flow, tags_map.get(flow.id, []))

    async def update_flow(self, flow_id: UUID, body: FlowUpdate) -> FlowOut:
        """更新流程元信息与标签（标签为全量替换）。"""
        flow = await self._get_flow_or_raise(flow_id)
        data = body.model_dump(exclude_unset=True)
        tag_ids = data.pop("tag_ids", None)
        await self.repo.update_fields(flow, data)
        await self.db.flush()
        if tag_ids is not None:
            await TagService(self.db, self.ctx).replace_entity_tags(TagEntityType.FLOW, flow.id, tag_ids)
        await self.db.refresh(flow)
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.FLOW, {flow.id})
        return self._to_out(flow, tags_map.get(flow.id, []))

    async def delete_flow(self, flow_id: UUID) -> None:
        """软删除流程：先清标签与级联依赖，再打删除标记。"""
        flow = await self._get_flow_or_raise(flow_id)
        await TagService(self.db, self.ctx).clear_entity_tags(TagEntityType.FLOW, flow.id)
        await before_delete_flow(self.db, flow.id)
        await mark_deleted(self.db, flow)

