"""智能体 CRUD 与详情加载。

创建/更新时同步 KB 绑定、子 Agent、A2A peer、标签；删除走 ``before_delete_agent`` 级联。
``export_package`` / ``import_package`` 支持 JSON 包迁移（不含 KB 文档内容）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundError
from app.common.schema import PageParams, PageResult
from app.core.service import BaseService
from app.core.soft_delete import append_not_deleted, is_marked_deleted, mark_deleted
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.deletion.cascade import before_delete_agent
from app.models.agent import Agent, AgentStatus, AgentSubAgentBinding, AgentType
from app.models.category import CategoryDomain
from app.models.tag import TagEntityType
from app.tenant.a2a.services.host_bindings import (
    normalize_host_peers,
    validate_and_sync_host_peer_bindings,
)
from app.tenant.a2a.services.peer_refs import (
    normalize_peer_refs,
    validate_and_sync_agent_a2a_peer_refs,
)
from app.tenant.agents.meta import agents_meta_dict
from app.tenant.agents.repositories.agent import AgentRepository
from app.tenant.agents.schemas.agent import AgentCreate, AgentOut, AgentUpdate
from app.tenant.agents.schemas.meta import AgentMetaOut
from app.tenant.agents.services.agent.serialization import agent_out
from app.tenant.agents.services.context import build_skill_mcp_prompt_block
from app.tenant.agents.services.sub_agents import (
    apply_planner_config,
    list_sub_agent_bindings,
    normalize_bindings,
    validate_agent_type_constraints,
    validate_and_sync_sub_agents,
)
from app.tenant.categories.services.category import CategoryService
from app.tenant.prompts.models import PromptTemplate
from app.tenant.tags.services.tag import TagService

if TYPE_CHECKING:
    from app.tenant.agents.schemas.agent import AgentPackage


class AgentCrudMixin(BaseService):
    """智能体元数据、CRUD 与 system_prompt 解析。"""

    repo: AgentRepository

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        """注入租户上下文并初始化 ``AgentRepository``。"""
        super().__init__(db, ctx)
        self.repo = AgentRepository(db)

    async def get_meta(self) -> AgentMetaOut:
        """返回枚举展示字典（无 DB 查询，文案来自 tenant/*/meta.py）。"""
        return AgentMetaOut.model_validate(agents_meta_dict())

    async def resolve_system_prompt(self, agent: Agent) -> str:
        """合并智能体 system_prompt 与技能/MCP 说明块。"""
        if agent.system_prompt and agent.system_prompt.strip():
            base = agent.system_prompt.strip()
        elif agent.prompt_template_id:
            tpl = await self.db.get(PromptTemplate, agent.prompt_template_id)
            if tpl and tpl.is_active and not is_marked_deleted(tpl):
                base = tpl.content
            else:
                base = "你是企业智能助手，请准确、简洁地回答用户问题。"
        else:
            base = "你是企业智能助手，请准确、简洁地回答用户问题。"
        extras = await build_skill_mcp_prompt_block(self.db, self.ctx, agent.config or {})
        if extras:
            return f"{base}\n\n{extras}"
        return base

    async def get_agent_or_raise(self, agent_id: UUID) -> Agent:
        """加载详情（含 KB/子 Agent 关联）并校验租户。"""
        agent = await self.repo.get_detail(agent_id)
        if not agent or is_marked_deleted(agent):
            raise NotFoundError("智能体不存在")
        assert_tenant_access(self.ctx, agent.tenant_id)
        return agent

    async def list_agents(
        self,
        params: PageParams,
        *,
        agent_type: AgentType | None = None,
        category_id: UUID | None = None,
        tag_ids: list[UUID] | None = None,
    ) -> PageResult[AgentOut]:
        """分页列出智能体，可按 agent_type、category_id 过滤。"""
        from sqlalchemy.orm import selectinload
        from app.models.agent import Agent as AgentModel

        filters = append_not_deleted(
            tenant_filters(self.ctx, AgentModel.tenant_id),
            AgentModel,
        )
        if agent_type is not None:
            filters.append(AgentModel.agent_type == agent_type)
        if category_id is not None:
            filters.append(AgentModel.category_id == category_id)
        tag_subq = TagService(self.db, self.ctx).entity_id_filter(TagEntityType.AGENT, tag_ids or [])
        if tag_subq is not None:
            filters.append(AgentModel.id.in_(tag_subq))
        page = await self.repo.list_page(
            page=params.page,
            size=params.size,
            filters=filters,
            order_by=AgentModel.created_at.desc(),
            options=[
                selectinload(AgentModel.knowledge_bases),
                selectinload(AgentModel.sub_agent_bindings).selectinload(AgentSubAgentBinding.child_agent),
            ],
        )
        cat_ids = {a.category_id for a in page.items if a.category_id}
        cat_names = await CategoryService(self.db, self.ctx).get_category_name_map(CategoryDomain.AGENT, cat_ids)
        entity_ids = {a.id for a in page.items}
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.AGENT, entity_ids)
        items = []
        for a in page.items:
            items.append(
                await agent_out(
                    self,
                    a,
                    category_names=cat_names,
                    tag_refs=tags_map.get(a.id, []),
                )
            )
        return PageResult(
            items=items,
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def create_agent(self, body: AgentCreate) -> AgentOut:
        """创建智能体并同步 KB、子 Agent、A2A peer、标签绑定。"""
        from app.tenant.system.services.quota import assert_can_create_agent

        await assert_can_create_agent(self.db, self.ctx.tenant_id)
        await CategoryService(self.db, self.ctx).validate_category_for_domain(body.category_id, CategoryDomain.AGENT)
        validate_agent_type_constraints(
            agent_type=body.agent_type,
            kb_ids=body.kb_ids,
            published_flow_id=body.published_flow_id,
            sub_agents=body.sub_agents,
            a2a_peers=body.a2a_peers,
            model_config_id=body.model_config_id,
            is_create=True,
        )
        agent = await self.repo.create(
            tenant_id=self.ctx.tenant_id,
            agent_type=body.agent_type,
            category_id=body.category_id,
            name=body.name,
            description=body.description,
            system_prompt=body.system_prompt,
            prompt_template_id=body.prompt_template_id,
            model_config_id=body.model_config_id,
            published_flow_id=body.published_flow_id,
            config=body.config,
            status=AgentStatus.ENABLED,
        )
        if body.kb_ids:
            await self.repo.replace_kb_bindings(agent.id, body.kb_ids, tenant_id=self.ctx.tenant_id)
        bindings = normalize_bindings([b.model_dump() for b in body.sub_agents] if body.sub_agents else None)
        agent.config = apply_planner_config(body.config, has_sub_agents=bool(bindings))
        await validate_and_sync_sub_agents(self.db, self.ctx, agent, bindings)
        a2a_raw_list = [p.model_dump() for p in body.a2a_peers] if body.a2a_peers else None
        if body.agent_type == AgentType.A2A:
            host_peers = normalize_host_peers(a2a_raw_list)
            await validate_and_sync_host_peer_bindings(self.db, self.ctx, agent, host_peers)
        else:
            a2a_raw = normalize_peer_refs(a2a_raw_list)
            await validate_and_sync_agent_a2a_peer_refs(self.db, self.ctx, agent, a2a_raw)
        await self.db.flush()
        if body.tag_ids:
            await TagService(self.db, self.ctx).replace_entity_tags(TagEntityType.AGENT, agent.id, body.tag_ids)
        await self.db.refresh(agent, ["knowledge_bases", "sub_agent_bindings"])
        agent = await self.get_agent_or_raise(agent.id)
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.AGENT, {agent.id})
        return await agent_out(self, agent, tag_refs=tags_map.get(agent.id, []))

    async def get_agent(self, agent_id: UUID) -> AgentOut:
        """按 ID 返回智能体详情（含分类名与标签）。"""
        agent = await self.get_agent_or_raise(agent_id)
        cat_names = await CategoryService(self.db, self.ctx).get_category_name_map(
            CategoryDomain.AGENT,
            {agent.category_id} if agent.category_id else set(),
        )
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.AGENT, {agent.id})
        return await agent_out(self, agent, category_names=cat_names, tag_refs=tags_map.get(agent.id, []))

    async def update_agent(self, agent_id: UUID, body: AgentUpdate) -> AgentOut:
        """部分更新智能体字段及 KB/子 Agent/A2A/标签绑定。"""
        agent = await self.get_agent_or_raise(agent_id)
        data = body.model_dump(exclude_unset=True)
        if "category_id" in data:
            await CategoryService(self.db, self.ctx).validate_category_for_domain(data.get("category_id"), CategoryDomain.AGENT)
        kb_ids = data.pop("kb_ids", None)
        tag_ids = data.pop("tag_ids", None)
        sub_raw = data.pop("sub_agents", None)
        a2a_raw_in = data.pop("a2a_peers", None)
        next_type = data.get("agent_type", agent.agent_type)
        if isinstance(next_type, str):
            next_type = AgentType(next_type)
        validate_agent_type_constraints(
            agent_type=next_type,
            kb_ids=kb_ids,
            published_flow_id=data.get("published_flow_id"),
            sub_agents=sub_raw,
            a2a_peers=a2a_raw_in,
            model_config_id=data.get("model_config_id", agent.model_config_id),
        )
        await self.repo.update_fields(agent, data)
        if kb_ids is not None:
            await self.repo.replace_kb_bindings(agent.id, kb_ids, tenant_id=self.ctx.tenant_id)
        if sub_raw is not None:
            bindings = normalize_bindings([b.model_dump() if hasattr(b, "model_dump") else b for b in sub_raw])
            agent.config = apply_planner_config(
                data.get("config") or agent.config,
                has_sub_agents=bool(bindings),
            )
            await validate_and_sync_sub_agents(self.db, self.ctx, agent, bindings)
        elif "config" in data:
            existing = await list_sub_agent_bindings(self.db, agent_id)
            agent.config = apply_planner_config(data["config"], has_sub_agents=bool(existing))
        if a2a_raw_in is not None:
            raw_list = [p.model_dump() if hasattr(p, "model_dump") else p for p in a2a_raw_in]
            if agent.agent_type == AgentType.A2A:
                await validate_and_sync_host_peer_bindings(self.db, self.ctx, agent, normalize_host_peers(raw_list))
            else:
                await validate_and_sync_agent_a2a_peer_refs(self.db, self.ctx, agent, normalize_peer_refs(raw_list))
        await self.db.flush()
        if tag_ids is not None:
            await TagService(self.db, self.ctx).replace_entity_tags(TagEntityType.AGENT, agent_id, tag_ids)
        agent = await self.get_agent_or_raise(agent_id)
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.AGENT, {agent_id})
        return await agent_out(self, agent, tag_refs=tags_map.get(agent_id, []))

    async def delete_agent(self, agent_id: UUID) -> None:
        """级联解绑后软删智能体。"""
        agent = await self.get_agent_or_raise(agent_id)
        await TagService(self.db, self.ctx).clear_entity_tags(TagEntityType.AGENT, agent.id)
        await before_delete_agent(self.db, agent.id)
        await mark_deleted(self.db, agent)

    async def export_package(self, agent_id: UUID) -> "AgentPackage":
        """导出智能体为可移植 JSON 包。"""
        from sqlalchemy import select
        from app.models.agent import agent_kb_bindings
        from app.tenant.agents.schemas.agent import AgentPackage

        agent = await self.get_agent_or_raise(agent_id)
        rows = await self.db.execute(select(agent_kb_bindings.c.kb_id).where(agent_kb_bindings.c.agent_id == agent_id))
        kb_ids = [row[0] for row in rows.all()]

        body = AgentCreate(
            agent_type=agent.agent_type,
            name=agent.name,
            description=agent.description or "",
            system_prompt=agent.system_prompt,
            model_config_id=agent.model_config_id,
            prompt_template_id=agent.prompt_template_id,
            published_flow_id=agent.published_flow_id,
            category_id=agent.category_id,
            config=agent.config or {},
            kb_ids=kb_ids,
        )
        return AgentPackage(version="1.0", agent=body)

    async def import_package(self, pkg: "AgentPackage") -> "AgentOut":
        """从 JSON 包导入智能体。"""
        return await self.create_agent(pkg.agent)
