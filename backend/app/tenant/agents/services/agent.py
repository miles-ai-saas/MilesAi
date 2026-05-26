"""
智能体 CRUD 与对话编排（L2）。

``chat`` 决策顺序（自上而下命中即返回）
-------------------------------------
1. A2A Host 模式（``agent_type=a2a`` 等）
2. 子智能体绑定 → DeepAgents 规划
3. A2A Peer 增强（有 peer 且无子 Agent 时）
4. ``published_flow_id`` → 流程画布运行时（``RunContext.kb_ids`` 传入节点）
5. 默认 **RAG**：``_rag_chat`` → LangGraph 或线性 ``rag_answer``

RAG 与知识库
------------
- ``agent.knowledge_bases`` 经 ``agt_kb_bindings`` 多对多关联
- 检索走 ``integrations.langchain.vectorstores.search_multi_kb_async``（各 KB 独立 embed）
- ``config.top_k``、``use_langgraph_rag``、``runtime_mode`` 等控制检索与生成路径
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.generate import format_hits_context, rag_answer, retrieve_hits
from app.integrations.langgraph.runner import run_rag_workflow, should_use_langgraph_rag
from app.integrations.langchain.chat_models import ainvoke_chat
from app.common.exceptions import BadRequestError, NotFoundError
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.flow_runtime.runtime_factory import get_flow_runtime
from app.flow_runtime.types import RunContext
from app.tenant.prompts.models import PromptTemplate
from app.models.agent import Agent, AgentStatus, AgentSubAgentBinding, AgentType
from app.models.category import CategoryDomain
from app.tenant.categories.services.category import CategoryService
from app.models.tag import TagEntityType
from app.tenant.tags.services.tag import TagService
from app.tenant.agents.repositories.agent import AgentRepository
from app.tenant.hooks.models import HookScope, HookTrigger
from app.tenant.hooks.services.runner import HookRunner
from app.tenant.flows.repositories.flow import FlowRepository
from app.tenant.agents.schemas.agent import (
    A2aPeerRefOut,
    AgentCreate,
    AgentOut,
    AgentUpdate,
    ChatRequest,
    ChatResponse,
    SubAgentRefOut,
)
from app.tenant.a2a.services.host_bindings import (
    list_host_peer_bindings,
    normalize_host_peers,
    validate_and_sync_host_peer_bindings,
)
from app.tenant.a2a.services.peer_refs import (
    list_agent_a2a_peer_refs,
    list_all_agent_a2a_peer_refs,
    normalize_peer_refs,
    validate_and_sync_agent_a2a_peer_refs,
)
from app.tenant.agents.meta import agents_meta_dict
from app.tenant.agents.schemas.meta import AgentMetaOut
from app.tenant.agents.services.sub_agents import (
    apply_planner_config,
    list_sub_agent_bindings,
    normalize_bindings,
    validate_agent_type_constraints,
    validate_and_sync_sub_agents,
)
from app.common.schema import PageParams, PageResult
from app.core.soft_delete import append_not_deleted, is_marked_deleted, mark_deleted, not_deleted
from app.core.service import BaseService
from app.tenant.agents.services.context import build_skill_mcp_prompt_block
from app.tenant.compliance.services.compliance import ComplianceService
from app.deletion.cascade import before_delete_agent


def should_use_skill_tools_with_kb(agent: Agent, kb_ids: list[str]) -> bool:
    """绑定 KB 且同时绑定技能包并开启 tool calling 时，走 tool_agent（含 skill_* 与 knowledge_search）。"""
    cfg = agent.config if isinstance(agent.config, dict) else {}
    return bool(
        kb_ids
        and agent.model_config_id
        and cfg.get("enable_tool_calling")
        and cfg.get("skill_package_id")
    )


def _sub_agents_out(agent: Agent) -> list[SubAgentRefOut]:
    refs: list[SubAgentRefOut] = []
    for b in sorted(agent.sub_agent_bindings or [], key=lambda x: x.sort_order):
        child = b.child_agent
        if not child:
            continue
        refs.append(
            SubAgentRefOut(
                id=child.id,
                name=child.name,
                role_hint=b.role_hint,
                status=child.status,
                description=child.description,
            )
        )
    return refs


def _a2a_peers_out_from_rows(refs: list) -> list[A2aPeerRefOut]:
    out: list[A2aPeerRefOut] = []
    for ref in refs:
        peer = ref.peer
        if not peer:
            continue
        kws = ref.trigger_keywords if isinstance(ref.trigger_keywords, list) else []
        out.append(
            A2aPeerRefOut(
                id=peer.id,
                name=peer.name,
                role_hint=ref.role_hint,
                trigger_keywords=[str(k) for k in kws],
                enabled=ref.enabled,
                status=peer.status.value,
                card_display_name=peer.card_display_name,
                agent_card_url=peer.agent_card_url,
            )
        )
    return out


def _bindings_to_a2a_out(bindings: list) -> list[A2aPeerRefOut]:
    return _a2a_peers_out_from_rows(bindings)


async def _agent_out(
    svc: AgentService,
    agent: Agent,
    *,
    category_names: dict[UUID, str] | None = None,
    tag_refs: list | None = None,
) -> AgentOut:
    if agent.agent_type == AgentType.A2A:
        bindings = await list_host_peer_bindings(svc.db, agent.id)
        a2a_out = _bindings_to_a2a_out(bindings)
    else:
        refs = await list_all_agent_a2a_peer_refs(svc.db, agent.id)
        a2a_out = _a2a_peers_out_from_rows(refs)
    cat_name = None
    if agent.category_id and category_names:
        cat_name = category_names.get(agent.category_id)
    return AgentOut(
        id=agent.id,
        tenant_id=agent.tenant_id,
        agent_type=agent.agent_type,
        category_id=agent.category_id,
        category_name=cat_name,
        tags=tag_refs or [],
        name=agent.name,
        description=agent.description,
        status=agent.status,
        system_prompt=agent.system_prompt,
        prompt_template_id=agent.prompt_template_id,
        model_config_id=agent.model_config_id,
        published_flow_id=agent.published_flow_id,
        kb_ids=[kb.id for kb in agent.knowledge_bases],
        sub_agents=_sub_agents_out(agent),
        a2a_peers=a2a_out,
        config=agent.config or {},
        created_at=agent.created_at,
    )


class AgentService(BaseService):
    """智能体 CRUD；chat 按类型路由 A2A/子 Agent/流程/RAG。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = AgentRepository(db)
        self.flow_repo = FlowRepository(db)

    async def get_meta(self) -> AgentMetaOut:
        """返回枚举展示字典（无 DB 查询，文案来自 tenant/*/meta.py）。"""
        return AgentMetaOut.model_validate(agents_meta_dict())

    async def _resolve_system_prompt(self, agent: Agent) -> str:
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

    async def _flow_run_context(
        self,
        agent: Agent,
        *,
        agent_id: UUID,
        inputs: dict,
        kb_ids: list[str],
    ) -> RunContext:
        return RunContext(
            tenant_id=str(self.ctx.tenant_id),
            inputs=inputs,
            kb_ids=kb_ids,
            model_config_id=str(agent.model_config_id) if agent.model_config_id else None,
            system_prompt=await self._resolve_system_prompt(agent),
            user_id=str(self.ctx.user_id),
            permissions=self.ctx.permissions,
            is_superuser=self.ctx.is_superuser,
            agent_id=str(agent_id),
            agent_config=dict(agent.config or {}),
        )

    async def _get_agent_or_raise(self, agent_id: UUID) -> Agent:
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
        tag_subq = TagService(self.db, self.ctx).entity_id_filter(
            TagEntityType.AGENT, tag_ids or []
        )
        if tag_subq is not None:
            filters.append(AgentModel.id.in_(tag_subq))
        page = await self.repo.list_page(
            page=params.page,
            size=params.size,
            filters=filters,
            order_by=AgentModel.created_at.desc(),
            options=[
                selectinload(AgentModel.knowledge_bases),
                selectinload(AgentModel.sub_agent_bindings).selectinload(
                    AgentSubAgentBinding.child_agent
                ),
            ],
        )
        cat_ids = {a.category_id for a in page.items if a.category_id}
        cat_names = await CategoryService(self.db, self.ctx).get_category_name_map(
            CategoryDomain.AGENT, cat_ids
        )
        entity_ids = {a.id for a in page.items}
        tags_map = await TagService(self.db, self.ctx).get_refs_map(
            TagEntityType.AGENT, entity_ids
        )
        items = []
        for a in page.items:
            items.append(
                await _agent_out(
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
        """创建智能体并同步 KB/子 Agent/A2A 绑定。"""
        await CategoryService(self.db, self.ctx).validate_category_for_domain(
            body.category_id, CategoryDomain.AGENT
        )
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
            await self.repo.replace_kb_bindings(
                agent.id, body.kb_ids, tenant_id=self.ctx.tenant_id
            )
        bindings = normalize_bindings(
            [b.model_dump() for b in body.sub_agents] if body.sub_agents else None
        )
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
            await TagService(self.db, self.ctx).replace_entity_tags(
                TagEntityType.AGENT, agent.id, body.tag_ids
            )
        await self.db.refresh(agent, ["knowledge_bases", "sub_agent_bindings"])
        agent = await self._get_agent_or_raise(agent.id)
        tags_map = await TagService(self.db, self.ctx).get_refs_map(
            TagEntityType.AGENT, {agent.id}
        )
        return await _agent_out(self, agent, tag_refs=tags_map.get(agent.id, []))

    async def get_agent(self, agent_id: UUID) -> AgentOut:
        agent = await self._get_agent_or_raise(agent_id)
        cat_names = await CategoryService(self.db, self.ctx).get_category_name_map(
            CategoryDomain.AGENT,
            {agent.category_id} if agent.category_id else set(),
        )
        tags_map = await TagService(self.db, self.ctx).get_refs_map(
            TagEntityType.AGENT, {agent.id}
        )
        return await _agent_out(
            self, agent, category_names=cat_names, tag_refs=tags_map.get(agent.id, [])
        )

    async def update_agent(self, agent_id: UUID, body: AgentUpdate) -> AgentOut:
        agent = await self._get_agent_or_raise(agent_id)
        data = body.model_dump(exclude_unset=True)
        if "category_id" in data:
            await CategoryService(self.db, self.ctx).validate_category_for_domain(
                data.get("category_id"), CategoryDomain.AGENT
            )
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
            await self.repo.replace_kb_bindings(
                agent.id, kb_ids, tenant_id=self.ctx.tenant_id
            )
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
                await validate_and_sync_host_peer_bindings(
                    self.db, self.ctx, agent, normalize_host_peers(raw_list)
                )
            else:
                await validate_and_sync_agent_a2a_peer_refs(
                    self.db, self.ctx, agent, normalize_peer_refs(raw_list)
                )
        await self.db.flush()
        if tag_ids is not None:
            await TagService(self.db, self.ctx).replace_entity_tags(
                TagEntityType.AGENT, agent_id, tag_ids
            )
        agent = await self._get_agent_or_raise(agent_id)
        tags_map = await TagService(self.db, self.ctx).get_refs_map(
            TagEntityType.AGENT, {agent_id}
        )
        return await _agent_out(self, agent, tag_refs=tags_map.get(agent_id, []))

    async def _maybe_augment_a2a(
        self, agent: Agent, body: ChatRequest, response: ChatResponse
    ) -> ChatResponse:
        """若配置了 A2A peer，在已有回答上追加外部智能体增强。"""
        refs = await list_agent_a2a_peer_refs(self.db, agent.id)
        if not refs:
            return response
        from app.tenant.a2a.invoke import augment_response_with_a2a

        return await augment_response_with_a2a(self, agent, body, response)

    async def delete_agent(self, agent_id: UUID) -> None:
        """级联解绑后软删智能体。"""
        agent = await self._get_agent_or_raise(agent_id)
        await TagService(self.db, self.ctx).clear_entity_tags(TagEntityType.AGENT, agent.id)
        await before_delete_agent(self.db, agent.id)
        await mark_deleted(self.db, agent)

    async def chat(self, agent_id: UUID, body: ChatRequest) -> ChatResponse:
        """租户侧智能体对话入口：合规与 Hook 包裹整条调用链。"""
        agent = await self._get_agent_or_raise(agent_id)
        if agent.status != AgentStatus.ENABLED:
            raise BadRequestError("智能体已禁用")

        compliance = ComplianceService(self.db, self.ctx)
        hooks = HookRunner(self.db, self.ctx.tenant_id)
        hook_payload = {
            "module": "agent_chat",
            "agent_id": str(agent_id),
            "query": body.query,
        }

        try:
            before_call = await hooks.run(
                HookTrigger.BEFORE_CALL,
                HookScope.AGENT,
                agent_id,
                {**hook_payload, "direction": "in"},
            )
            hook_payload = before_call.payload
            query = str(hook_payload.get("query", body.query))
            chat_body = body.model_copy(update={"query": query}) if query != body.query else body
            await compliance.check_input(query, module="agent_chat")

            if agent.agent_type == AgentType.A2A:
                from app.tenant.a2a.invoke import run_a2a_host_chat

                response = await run_a2a_host_chat(self, agent, chat_body)
                await compliance.check_output(response.answer, module="agent_chat")
                await hooks.run(
                    HookTrigger.AFTER_CALL,
                    HookScope.AGENT,
                    agent_id,
                    {**hook_payload, "direction": "out", "text": response.answer},
                )
                return response

            bindings = await list_sub_agent_bindings(self.db, agent_id)
            peer_refs = await list_agent_a2a_peer_refs(self.db, agent_id)
            if bindings:
                from app.integrations.deepagents.orchestrator import run_subagent_planned_chat

                response = await run_subagent_planned_chat(self, agent, bindings, chat_body)
                if peer_refs:
                    response = await self._maybe_augment_a2a(agent, chat_body, response)
                await compliance.check_output(response.answer, module="agent_chat")
                await hooks.run(
                    HookTrigger.AFTER_CALL,
                    HookScope.AGENT,
                    agent_id,
                    {**hook_payload, "direction": "out", "text": response.answer},
                )
                return response

            if peer_refs:
                from app.tenant.a2a.invoke import run_a2a_augmented_chat

                kb_ids = [str(kb.id) for kb in agent.knowledge_bases]
                top_k = int((agent.config or {}).get("top_k", 5))
                response = await run_a2a_augmented_chat(
                    self,
                    agent,
                    chat_body,
                    kb_ids=kb_ids,
                    top_k=top_k,
                    agent_id=agent_id,
                    hooks=hooks,
                )
                await compliance.check_output(response.answer, module="agent_chat")
                await hooks.run(
                    HookTrigger.AFTER_CALL,
                    HookScope.AGENT,
                    agent_id,
                    {**hook_payload, "direction": "out", "text": response.answer},
                )
                return response

            kb_ids = [str(kb.id) for kb in agent.knowledge_bases]
            top_k = int((agent.config or {}).get("top_k", 5))

            if agent.published_flow_id:
                flow = await self.flow_repo.get_by_id(agent.published_flow_id)
                if flow and flow.current_version > 0:
                    version = await self.flow_repo.get_version(flow.id, flow.current_version)
                    if version:
                        ctx = await self._flow_run_context(
                            agent,
                            agent_id=agent_id,
                            inputs={"query": query, **chat_body.inputs},
                            kb_ids=kb_ids,
                        )
                        result = await get_flow_runtime().run(version.graph_json, ctx)
                        response = ChatResponse(answer=str(result.output), steps=result.steps)
                        response = await self._maybe_augment_a2a(agent, chat_body, response)
                        await compliance.check_output(response.answer, module="agent_chat")
                        await hooks.run(
                            HookTrigger.AFTER_CALL,
                            HookScope.AGENT,
                            agent_id,
                            {**hook_payload, "direction": "out", "text": response.answer},
                        )
                        return response

            response = await self._rag_chat(agent, chat_body, kb_ids, top_k, agent_id, hooks)
            response = await self._maybe_augment_a2a(agent, chat_body, response)
            await compliance.check_output(response.answer, module="agent_chat")
            await hooks.run(
                HookTrigger.AFTER_CALL,
                HookScope.AGENT,
                agent_id,
                {**hook_payload, "direction": "out", "text": response.answer},
            )
            return response
        except Exception as exc:
            await hooks.run(
                HookTrigger.ON_ERROR,
                HookScope.AGENT,
                agent_id,
                {**hook_payload, "error": str(exc)},
            )
            raise

    async def chat_as_child(self, child_id: UUID, body: ChatRequest) -> ChatResponse:
        """子智能体工位：不再走子智能体规划，仅 RAG/流程/直连。"""
        child = await self._get_agent_or_raise(child_id)
        if child.status != AgentStatus.ENABLED:
            raise BadRequestError("子智能体已禁用")
        kb_ids = [str(kb.id) for kb in child.knowledge_bases]
        top_k = int((child.config or {}).get("top_k", 5))
        hooks = HookRunner(self.db, self.ctx.tenant_id)

        if child.published_flow_id:
            flow = await self.flow_repo.get_by_id(child.published_flow_id)
            if flow and flow.current_version > 0:
                version = await self.flow_repo.get_version(flow.id, flow.current_version)
                if version:
                    ctx = await self._flow_run_context(
                        child,
                        agent_id=child_id,
                        inputs={"query": body.query, **body.inputs},
                        kb_ids=kb_ids,
                    )
                    result = await get_flow_runtime().run(version.graph_json, ctx)
                    return ChatResponse(answer=str(result.output), steps=result.steps)

        return await self._rag_chat(child, body, kb_ids, top_k, child_id, hooks)

    async def _direct_chat(
        self,
        agent: Agent,
        body: ChatRequest,
        agent_id: UUID,
        hooks: HookRunner,
    ) -> ChatResponse:
        base = await self._resolve_system_prompt(agent)
        if agent.model_config_id and agent.model_config:
            before = await hooks.run(
                HookTrigger.BEFORE_REASONING,
                HookScope.AGENT,
                agent_id,
                {
                    "module": "agent_chat",
                    "agent_id": str(agent_id),
                    "mode": "direct",
                    "query": body.query,
                },
            )
            reasoning_query = str(before.payload.get("query", body.query))
            answer = await ainvoke_chat(
                agent.model_config,
                [
                    {"role": "system", "content": base},
                    {"role": "user", "content": reasoning_query},
                ],
                temperature=float((agent.config or {}).get("temperature", 0.7)),
                db=self.db,
                tenant_id=self.ctx.tenant_id,
            )
            await hooks.run(
                HookTrigger.AFTER_REASONING,
                HookScope.AGENT,
                agent_id,
                {"module": "agent_chat", "agent_id": str(agent_id), "text": answer[:500]},
            )
            return ChatResponse(answer=answer, sources=[])

        return ChatResponse(
            answer="当前智能体未配置大模型。请在「模型供应商」中配置并关联，或绑定知识库/流程后使用。",
            sources=[],
        )

    async def _rag_chat(
        self,
        agent: Agent,
        body: ChatRequest,
        kb_ids: list[str],
        top_k: int,
        agent_id: UUID,
        hooks: HookRunner,
    ) -> ChatResponse:
        """
        知识库增强对话。

        - 无 ``kb_ids``：可选 tool calling，否则 ``_direct_chat``
        - 有 KB + 大模型：``should_use_langgraph_rag`` 选 LangGraph 或 ``rag_answer``
        - 有 KB 无大模型：仅 ``retrieve_hits`` + 摘要文本（无生成）
        """
        if not kb_ids:
            if (agent.config or {}).get("enable_tool_calling") and agent.model_config_id:
                from app.integrations.langchain.tool_agent import run_tool_calling_chat

                base = await self._resolve_system_prompt(agent)
                return await run_tool_calling_chat(
                    self.db,
                    self.ctx,
                    agent,
                    body,
                    agent_id=agent_id,
                    system_prompt=base,
                )
            return await self._direct_chat(agent, body, agent_id, hooks)

        if should_use_skill_tools_with_kb(agent, kb_ids):
            from app.integrations.langchain.tool_agent import run_tool_calling_chat

            base = await self._resolve_system_prompt(agent)
            kb_hint = (
                "\n【知识库】请使用 knowledge_search 工具检索；"
                f"可用 kb_id：{', '.join(kb_ids)}"
            )
            return await run_tool_calling_chat(
                self.db,
                self.ctx,
                agent,
                body,
                agent_id=agent_id,
                system_prompt=f"{base}{kb_hint}",
            )

        base = await self._resolve_system_prompt(agent)

        if agent.model_config_id and agent.model_config:
            before = await hooks.run(
                HookTrigger.BEFORE_REASONING,
                HookScope.AGENT,
                agent_id,
                {
                    "module": "agent_chat",
                    "agent_id": str(agent_id),
                    "mode": "rag",
                    "query": body.query,
                    "query_preview": body.query[:200],
                },
            )
            reasoning_query = str(before.payload.get("query", body.query))
            temperature = float((agent.config or {}).get("temperature", 0.7))
            # 默认 LangGraph：检索 → 相关性评分 → 可选重试放大 top_k → 生成/兜底
            if should_use_langgraph_rag(agent, kb_ids=kb_ids):
                answer, all_hits, steps = await run_rag_workflow(
                    model=agent.model_config,
                    system_prompt=base,
                    query=reasoning_query,
                    kb_ids=kb_ids,
                    tenant_id=agent.tenant_id,
                    agent_id=agent_id,
                    top_k=top_k,
                    temperature=temperature,
                    agent_config=agent.config or {},
                    conversation_id=body.conversation_id,
                )
            else:
                answer, all_hits = await rag_answer(
                    model=agent.model_config,
                    system_prompt=base,
                    query=reasoning_query,
                    kb_ids=kb_ids,
                    tenant_id=agent.tenant_id,
                    db=self.db,
                    top_k=top_k,
                    temperature=temperature,
                )
                steps = [{"type": "rag_linear", "engine": "langchain"}]
            await hooks.run(
                HookTrigger.AFTER_REASONING,
                HookScope.AGENT,
                agent_id,
                {"module": "agent_chat", "agent_id": str(agent_id), "text": answer[:500]},
            )
        else:
            all_hits = await retrieve_hits(
                body.query,
                tenant_id=agent.tenant_id,
                kb_ids=kb_ids,
                db=self.db,
                top_k=top_k,
            )
            answer = f"（未配置大模型，以下为检索摘要）\n\n{format_hits_context(all_hits)}"
            steps = []

        return ChatResponse(answer=answer, sources=all_hits, steps=steps)
