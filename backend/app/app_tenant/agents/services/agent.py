from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag import format_hits_context, rag_answer, retrieve_hits
from app.ai_stack.langgraph.runner import run_rag_workflow, should_use_langgraph_rag
from app.ai_stack.langchain.chat_models import ainvoke_chat
from app.common.exceptions import BadRequestError, NotFoundError
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.flow_runtime.runtime_factory import get_flow_runtime
from app.flow_runtime.types import RunContext
from app.app_tenant.prompts.models import PromptTemplate
from app.models.agent import Agent, AgentStatus, AgentSubAgentBinding, AgentType
from app.app_tenant.agents.repositories.agent import AgentRepository
from app.app_tenant.hooks.models import HookScope, HookTrigger
from app.app_tenant.hooks.services.runner import HookRunner
from app.app_tenant.flows.repositories.flow import FlowRepository
from app.app_tenant.agents.schemas.agent import (
    A2aPeerRefOut,
    AgentCreate,
    AgentOut,
    AgentUpdate,
    ChatRequest,
    ChatResponse,
    SubAgentRefOut,
)
from app.app_tenant.a2a.services.host_bindings import (
    list_host_peer_bindings,
    normalize_host_peers,
    validate_and_sync_host_peer_bindings,
)
from app.app_tenant.a2a.services.peer_refs import (
    list_agent_a2a_peer_refs,
    list_all_agent_a2a_peer_refs,
    normalize_peer_refs,
    validate_and_sync_agent_a2a_peer_refs,
)
from app.app_tenant.agents.services.sub_agents import (
    apply_planner_config,
    list_sub_agent_bindings,
    normalize_bindings,
    validate_agent_type_constraints,
    validate_and_sync_sub_agents,
)
from app.common.schema import PageParams, PageResult
from app.core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from app.core.service import BaseService
from app.app_tenant.agents.services.context import build_skill_mcp_prompt_block
from app.app_tenant.compliance.services.compliance import ComplianceService
from app.deletion.cascade import before_delete_agent


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


async def _agent_out(svc: AgentService, agent: Agent) -> AgentOut:
    if agent.agent_type == AgentType.A2A:
        bindings = await list_host_peer_bindings(svc.db, agent.id)
        a2a_out = _bindings_to_a2a_out(bindings)
    else:
        refs = await list_all_agent_a2a_peer_refs(svc.db, agent.id)
        a2a_out = _a2a_peers_out_from_rows(refs)
    return AgentOut(
        id=agent.id,
        tenant_id=agent.tenant_id,
        agent_type=agent.agent_type,
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
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = AgentRepository(db)
        self.flow_repo = FlowRepository(db)

    async def _resolve_system_prompt(self, agent: Agent) -> str:
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

    async def _get_agent_or_raise(self, agent_id: UUID) -> Agent:
        agent = await self.repo.get_detail(agent_id)
        if not agent or is_marked_deleted(agent):
            raise NotFoundError("智能体不存在")
        assert_tenant_access(self.ctx, agent.tenant_id)
        return agent

    async def list_agents(
        self, params: PageParams, *, agent_type: AgentType | None = None
    ) -> PageResult[AgentOut]:
        from sqlalchemy.orm import selectinload
        from app.models.agent import Agent as AgentModel

        filters = tenant_filters(self.ctx, AgentModel.tenant_id)
        if agent_type is not None:
            filters.append(AgentModel.agent_type == agent_type)
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
        items = []
        for a in page.items:
            items.append(await _agent_out(self, a))
        return PageResult(
            items=items,
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def create_agent(self, body: AgentCreate) -> AgentOut:
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
            agent.knowledge_bases = await self.repo.load_kbs(body.kb_ids)
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
        await self.db.refresh(agent, ["knowledge_bases", "sub_agent_bindings"])
        agent = await self._get_agent_or_raise(agent.id)
        return await _agent_out(self, agent)

    async def get_agent(self, agent_id: UUID) -> AgentOut:
        agent = await self._get_agent_or_raise(agent_id)
        return await _agent_out(self, agent)

    async def update_agent(self, agent_id: UUID, body: AgentUpdate) -> AgentOut:
        agent = await self._get_agent_or_raise(agent_id)
        data = body.model_dump(exclude_unset=True)
        kb_ids = data.pop("kb_ids", None)
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
            agent.knowledge_bases = await self.repo.load_kbs(kb_ids)
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
        agent = await self._get_agent_or_raise(agent_id)
        return await _agent_out(self, agent)

    async def _maybe_augment_a2a(
        self, agent: Agent, body: ChatRequest, response: ChatResponse
    ) -> ChatResponse:
        refs = await list_agent_a2a_peer_refs(self.db, agent.id)
        if not refs:
            return response
        from app.app_tenant.a2a.invoke import augment_response_with_a2a

        return await augment_response_with_a2a(self, agent, body, response)

    async def delete_agent(self, agent_id: UUID) -> None:
        agent = await self._get_agent_or_raise(agent_id)
        await before_delete_agent(self.db, agent.id)
        await mark_deleted(self.db, agent)

    async def chat(self, agent_id: UUID, body: ChatRequest) -> ChatResponse:
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
            await hooks.run(
                HookTrigger.BEFORE_CALL,
                HookScope.AGENT,
                agent_id,
                {**hook_payload, "direction": "in"},
            )
            await compliance.check_input(body.query, module="agent_chat")

            if agent.agent_type == AgentType.A2A:
                from app.app_tenant.a2a.invoke import run_a2a_host_chat

                response = await run_a2a_host_chat(self, agent, body)
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
                from app.ai_stack.deepagents.orchestrator import run_subagent_planned_chat

                response = await run_subagent_planned_chat(self, agent, bindings, body)
                if peer_refs:
                    response = await self._maybe_augment_a2a(agent, body, response)
                await compliance.check_output(response.answer, module="agent_chat")
                await hooks.run(
                    HookTrigger.AFTER_CALL,
                    HookScope.AGENT,
                    agent_id,
                    {**hook_payload, "direction": "out", "text": response.answer},
                )
                return response

            if peer_refs:
                from app.app_tenant.a2a.invoke import run_a2a_augmented_chat

                kb_ids = [str(kb.id) for kb in agent.knowledge_bases]
                top_k = int((agent.config or {}).get("top_k", 5))
                response = await run_a2a_augmented_chat(
                    self,
                    agent,
                    body,
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
                        ctx = RunContext(
                            tenant_id=str(self.ctx.tenant_id),
                            inputs={"query": body.query, **body.inputs},
                            kb_ids=kb_ids,
                            model_config_id=str(agent.model_config_id) if agent.model_config_id else None,
                            system_prompt=await self._resolve_system_prompt(agent),
                        )
                        result = await get_flow_runtime().run(version.graph_json, ctx)
                        response = ChatResponse(answer=str(result.output), steps=result.steps)
                        response = await self._maybe_augment_a2a(agent, body, response)
                        await compliance.check_output(response.answer, module="agent_chat")
                        await hooks.run(
                            HookTrigger.AFTER_CALL,
                            HookScope.AGENT,
                            agent_id,
                            {**hook_payload, "direction": "out", "text": response.answer},
                        )
                        return response

            response = await self._rag_chat(agent, body, kb_ids, top_k, agent_id, hooks)
            response = await self._maybe_augment_a2a(agent, body, response)
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
                    ctx = RunContext(
                        tenant_id=str(self.ctx.tenant_id),
                        inputs={"query": body.query, **body.inputs},
                        kb_ids=kb_ids,
                        model_config_id=str(child.model_config_id) if child.model_config_id else None,
                        system_prompt=await self._resolve_system_prompt(child),
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
            await hooks.run(
                HookTrigger.BEFORE_REASONING,
                HookScope.AGENT,
                agent_id,
                {"module": "agent_chat", "agent_id": str(agent_id), "mode": "direct"},
            )
            answer = await ainvoke_chat(
                agent.model_config,
                [
                    {"role": "system", "content": base},
                    {"role": "user", "content": body.query},
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
        if not kb_ids:
            return await self._direct_chat(agent, body, agent_id, hooks)

        base = await self._resolve_system_prompt(agent)

        if agent.model_config_id and agent.model_config:
            await hooks.run(
                HookTrigger.BEFORE_REASONING,
                HookScope.AGENT,
                agent_id,
                {
                    "module": "agent_chat",
                    "agent_id": str(agent_id),
                    "mode": "rag",
                    "query_preview": body.query[:200],
                },
            )
            temperature = float((agent.config or {}).get("temperature", 0.7))
            if should_use_langgraph_rag(agent, kb_ids=kb_ids):
                answer, all_hits, steps = await run_rag_workflow(
                    model=agent.model_config,
                    system_prompt=base,
                    query=body.query,
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
                    query=body.query,
                    kb_ids=kb_ids,
                    tenant_id=agent.tenant_id,
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
                top_k=top_k,
            )
            answer = f"（未配置大模型，以下为检索摘要）\n\n{format_hits_context(all_hits)}"
            steps = []

        return ChatResponse(answer=answer, sources=all_hits, steps=steps)
