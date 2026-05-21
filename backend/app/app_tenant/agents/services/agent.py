from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embedding import embed_query
from app.common.exceptions import BadRequestError, NotFoundError
from app.core.llm_client import chat_completion
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.core.weaviate_store import search_vectors
from app.langflow.runtime_factory import get_flow_runtime
from app.langflow.types import RunContext
from app.app_tenant.prompts.models import PromptTemplate
from app.models.agent import Agent, AgentStatus
from app.app_tenant.agents.repositories.agent import AgentRepository
from app.app_tenant.hooks.models import HookScope, HookTrigger
from app.app_tenant.hooks.services.runner import HookRunner
from app.app_tenant.flows.repositories.flow import FlowRepository
from app.app_tenant.agents.schemas.agent import AgentCreate, AgentOut, AgentUpdate, ChatRequest, ChatResponse
from app.common.schema import PageParams, PageResult
from app.core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from app.core.service import BaseService
from app.app_tenant.agents.services.context import build_skill_mcp_prompt_block
from app.app_tenant.compliance.services.compliance import ComplianceService
from app.deletion.cascade import before_delete_agent


def _agent_out(agent: Agent) -> AgentOut:
    return AgentOut(
        id=agent.id,
        tenant_id=agent.tenant_id,
        name=agent.name,
        description=agent.description,
        status=agent.status,
        system_prompt=agent.system_prompt,
        prompt_template_id=agent.prompt_template_id,
        model_config_id=agent.model_config_id,
        published_flow_id=agent.published_flow_id,
        kb_ids=[kb.id for kb in agent.knowledge_bases],
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

    async def list_agents(self, params: PageParams) -> PageResult[AgentOut]:
        from sqlalchemy.orm import selectinload
        from app.models.agent import Agent as AgentModel

        filters = tenant_filters(self.ctx, AgentModel.tenant_id)
        page = await self.repo.list_page(
            page=params.page,
            size=params.size,
            filters=filters,
            order_by=AgentModel.created_at.desc(),
            options=[selectinload(AgentModel.knowledge_bases)],
        )
        return PageResult(
            items=[_agent_out(a) for a in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def create_agent(self, body: AgentCreate) -> AgentOut:
        agent = await self.repo.create(
            tenant_id=self.ctx.tenant_id,
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
        await self.db.flush()
        await self.db.refresh(agent, ["knowledge_bases"])
        return _agent_out(agent)

    async def get_agent(self, agent_id: UUID) -> AgentOut:
        agent = await self._get_agent_or_raise(agent_id)
        return _agent_out(agent)

    async def update_agent(self, agent_id: UUID, body: AgentUpdate) -> AgentOut:
        agent = await self._get_agent_or_raise(agent_id)
        data = body.model_dump(exclude_unset=True)
        kb_ids = data.pop("kb_ids", None)
        await self.repo.update_fields(agent, data)
        if kb_ids is not None:
            agent.knowledge_bases = await self.repo.load_kbs(kb_ids)
        await self.db.flush()
        await self.db.refresh(agent, ["knowledge_bases"])
        return _agent_out(agent)

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
                        runtime = get_flow_runtime()
                        result = await runtime.run(version.graph_json, ctx)
                        answer = str(result.output)
                        await compliance.check_output(answer, module="agent_chat")
                        await hooks.run(
                            HookTrigger.AFTER_CALL,
                            HookScope.AGENT,
                            agent_id,
                            {**hook_payload, "direction": "out", "text": answer},
                        )
                        return ChatResponse(answer=answer, steps=result.steps)

            response = await self._rag_chat(agent, body, kb_ids, top_k, agent_id, hooks)
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
            answer = await chat_completion(
                agent.model_config,
                [
                    {"role": "system", "content": base},
                    {"role": "user", "content": body.query},
                ],
                temperature=float((agent.config or {}).get("temperature", 0.7)),
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

        vector = embed_query(body.query)
        all_hits: list[dict] = []
        for kid in kb_ids:
            hits = search_vectors(
                vector,
                tenant_id=agent.tenant_id,
                kb_id=UUID(kid),
                limit=top_k,
            )
            all_hits.extend(hits)
        all_hits.sort(key=lambda h: h.get("score", 0), reverse=True)
        all_hits = all_hits[:top_k]

        context = "\n\n".join(
            f"[{h.get('score', 0):.2f}] {h.get('content_preview', '')}" for h in all_hits
        )
        base = await self._resolve_system_prompt(agent)
        prompt = f"{base}\n\n参考内容：\n{context}\n\n用户问题：{body.query}"

        if agent.model_config_id and agent.model_config:
            await hooks.run(
                HookTrigger.BEFORE_REASONING,
                HookScope.AGENT,
                agent_id,
                {"module": "agent_chat", "agent_id": str(agent_id), "prompt_preview": prompt[:500]},
            )
            answer = await chat_completion(
                agent.model_config,
                [{"role": "user", "content": prompt}],
                temperature=float((agent.config or {}).get("temperature", 0.7)),
            )
            await hooks.run(
                HookTrigger.AFTER_REASONING,
                HookScope.AGENT,
                agent_id,
                {"module": "agent_chat", "agent_id": str(agent_id), "text": answer[:500]},
            )
        else:
            answer = f"（未配置大模型，以下为检索摘要）\n\n{context}"

        return ChatResponse(answer=answer, sources=all_hits)
