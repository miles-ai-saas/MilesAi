"""智能体对话编排：A2A、子 Agent、流程画布、RAG。"""

from __future__ import annotations

from uuid import UUID

from app.common.exceptions import BadRequestError
from app.flow_runtime.runtime_factory import get_flow_runtime
from app.flow_runtime.types import RunContext
from app.integrations.chat.multimodal import build_user_message, resolve_media_refs
from app.integrations.langchain.chat_models import ainvoke_chat
from app.integrations.langgraph.runner import run_rag_workflow, should_use_langgraph_rag
from app.models.agent import Agent, AgentStatus, AgentType
from app.rag.generate import format_hits_context, rag_answer, retrieve_hits
from app.tenant.a2a.services.peer_refs import list_agent_a2a_peer_refs
from app.tenant.agents.schemas.agent import ChatRequest, ChatResponse
from app.tenant.agents.services.agent.serialization import should_use_skill_tools_with_kb
from app.tenant.agents.services.sub_agents import list_sub_agent_bindings
from app.tenant.compliance.constants import SCAN_MODULE_AGENT_CHAT
from app.tenant.compliance.services.compliance import ComplianceService
from app.tenant.flows.repositories.flow import FlowRepository
from app.tenant.hooks.models import HookScope, HookTrigger
from app.tenant.hooks.services.runner import HookRunner


class AgentChatMixin:
    """对话路由与 RAG；依赖 AgentCrudMixin 的加载与 prompt 解析。"""

    flow_repo: FlowRepository

    async def flow_run_context(
        self,
        agent: Agent,
        *,
        agent_id: UUID,
        inputs: dict,
        kb_ids: list[str],
        media: list | None = None,
    ) -> RunContext:
        """构造流程画布 ``RunContext``（含 system_prompt、KB、附图 payload）。"""
        media_payload: list[dict] = []
        if media:
            for m in media:
                if hasattr(m, "model_dump"):
                    media_payload.append(m.model_dump(mode="json"))
                elif isinstance(m, dict):
                    media_payload.append(m)
        return RunContext(
            tenant_id=str(self.ctx.tenant_id),
            inputs=inputs,
            kb_ids=kb_ids,
            model_config_id=str(agent.model_config_id) if agent.model_config_id else None,
            system_prompt=await self.resolve_system_prompt(agent),
            user_id=str(self.ctx.user_id),
            permissions=self.ctx.permissions,
            is_superuser=self.ctx.is_superuser,
            agent_id=str(agent_id),
            agent_config=dict(agent.config or {}),
            media=media_payload,
        )

    async def maybe_augment_a2a(
        self, agent: Agent, body: ChatRequest, response: ChatResponse
    ) -> ChatResponse:
        """若配置了 A2A peer，在已有回答上追加外部智能体增强。"""
        refs = await list_agent_a2a_peer_refs(self.db, agent.id)
        if not refs:
            return response
        from app.tenant.a2a.invoke import augment_response_with_a2a

        return await augment_response_with_a2a(self, agent, body, response)

    async def _finish_chat_turn(
        self,
        *,
        compliance: ComplianceService,
        hooks: HookRunner,
        agent_id: UUID,
        hook_payload: dict,
        response: ChatResponse,
    ) -> ChatResponse:
        """单轮对话收尾：出站合规校验 + ``AFTER_CALL`` Hook。"""
        await compliance.check_output(response.answer, module=SCAN_MODULE_AGENT_CHAT)
        await hooks.run(
            HookTrigger.AFTER_CALL,
            HookScope.AGENT,
            agent_id,
            {**hook_payload, "direction": "out", "text": response.answer},
        )
        return response

    async def chat(self, agent_id: UUID, body: ChatRequest) -> ChatResponse:
        """租户侧智能体对话入口：合规与 Hook 包裹整条调用链。"""
        agent = await self.get_agent_or_raise(agent_id)
        if agent.status != AgentStatus.ENABLED:
            raise BadRequestError("智能体已禁用")

        compliance = ComplianceService(self.db, self.ctx)
        hooks = HookRunner(self.db, self.ctx.tenant_id)
        effective_query = body.query.strip() or ("[附图]" if body.media else "")
        hook_payload = {
            "module": SCAN_MODULE_AGENT_CHAT,
            "agent_id": str(agent_id),
            "query": effective_query,
            "media_count": len(body.media),
            "attachment_ids": [str(m.attachment_id) for m in body.media],
        }

        try:
            before_call = await hooks.run(
                HookTrigger.BEFORE_CALL,
                HookScope.AGENT,
                agent_id,
                {**hook_payload, "direction": "in"},
            )
            hook_payload = before_call.payload
            query = str(hook_payload.get("query", effective_query))
            chat_body = (
                body.model_copy(update={"query": query}) if query != effective_query else body
            )
            await compliance.check_input(query, module=SCAN_MODULE_AGENT_CHAT)

            if agent.agent_type == AgentType.A2A:
                from app.tenant.a2a.invoke import run_a2a_host_chat

                response = await run_a2a_host_chat(self, agent, chat_body)
                return await self._finish_chat_turn(
                    compliance=compliance,
                    hooks=hooks,
                    agent_id=agent_id,
                    hook_payload=hook_payload,
                    response=response,
                )

            bindings = await list_sub_agent_bindings(self.db, agent_id)
            peer_refs = await list_agent_a2a_peer_refs(self.db, agent_id)
            if bindings:
                from app.integrations.deepagents.orchestrator import run_subagent_planned_chat

                response = await run_subagent_planned_chat(self, agent, bindings, chat_body)
                if peer_refs:
                    response = await self.maybe_augment_a2a(agent, chat_body, response)
                return await self._finish_chat_turn(
                    compliance=compliance,
                    hooks=hooks,
                    agent_id=agent_id,
                    hook_payload=hook_payload,
                    response=response,
                )

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
                return await self._finish_chat_turn(
                    compliance=compliance,
                    hooks=hooks,
                    agent_id=agent_id,
                    hook_payload=hook_payload,
                    response=response,
                )

            kb_ids = [str(kb.id) for kb in agent.knowledge_bases]
            top_k = int((agent.config or {}).get("top_k", 5))

            if agent.published_flow_id:
                flow = await self.flow_repo.get_by_id(agent.published_flow_id)
                if flow and flow.current_version > 0:
                    version = await self.flow_repo.get_version(flow.id, flow.current_version)
                    if version:
                        flow_inputs = {"query": query, **chat_body.inputs}
                        if not str(flow_inputs.get("query", "")).strip() and chat_body.media:
                            flow_inputs["query"] = "请根据附图回答。"
                        ctx = await self.flow_run_context(
                            agent,
                            agent_id=agent_id,
                            inputs=flow_inputs,
                            kb_ids=kb_ids,
                            media=chat_body.media,
                        )
                        result = await get_flow_runtime().run(version.graph_json, ctx)
                        response = ChatResponse(answer=str(result.output), steps=result.steps)
                        response = await self.maybe_augment_a2a(agent, chat_body, response)
                        return await self._finish_chat_turn(
                            compliance=compliance,
                            hooks=hooks,
                            agent_id=agent_id,
                            hook_payload=hook_payload,
                            response=response,
                        )

            response = await self.rag_chat(agent, chat_body, kb_ids, top_k, agent_id, hooks)
            response = await self.maybe_augment_a2a(agent, chat_body, response)
            return await self._finish_chat_turn(
                compliance=compliance,
                hooks=hooks,
                agent_id=agent_id,
                hook_payload=hook_payload,
                response=response,
            )
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
        child = await self.get_agent_or_raise(child_id)
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
                    child_inputs = {"query": body.query, **body.inputs}
                    if not str(child_inputs.get("query", "")).strip() and body.media:
                        child_inputs["query"] = "请根据附图回答。"
                    ctx = await self.flow_run_context(
                        child,
                        agent_id=child_id,
                        inputs=child_inputs,
                        kb_ids=kb_ids,
                        media=body.media,
                    )
                    result = await get_flow_runtime().run(version.graph_json, ctx)
                    return ChatResponse(answer=str(result.output), steps=result.steps)

        return await self.rag_chat(child, body, kb_ids, top_k, child_id, hooks)

    async def resolve_chat_media_parts(self, agent: Agent, body: ChatRequest) -> tuple[str, list]:
        """解析附图，返回生成用 query 文本与 multimodal content parts。"""
        max_media = int((agent.config or {}).get("max_media_per_turn", 4))
        parts: list = []
        if body.media:
            parts = await resolve_media_refs(
                self.db, self.ctx, body.media, max_count=max_media
            )
        query = body.query.strip() or ("请根据附图回答。" if parts else body.query.strip())
        return query, parts

    async def direct_chat(
        self,
        agent: Agent,
        body: ChatRequest,
        agent_id: UUID,
        hooks: HookRunner,
    ) -> ChatResponse:
        """无知识库时直连大模型（可选 reasoning Hook）。"""
        base = await self.resolve_system_prompt(agent)
        if agent.model_config_id and agent.model_config:
            before = await hooks.run(
                HookTrigger.BEFORE_REASONING,
                HookScope.AGENT,
                agent_id,
                {
                    "module": SCAN_MODULE_AGENT_CHAT,
                    "agent_id": str(agent_id),
                    "mode": "direct",
                    "query": body.query,
                },
            )
            reasoning_query = str(before.payload.get("query", body.query))
            chat_query, media_parts = await self.resolve_chat_media_parts(agent, body)
            if reasoning_query == body.query:
                reasoning_query = chat_query
            user_msg = build_user_message(query=reasoning_query, media_parts=media_parts)
            answer = await ainvoke_chat(
                agent.model_config,
                [
                    {"role": "system", "content": base},
                    user_msg,
                ],
                temperature=float((agent.config or {}).get("temperature", 0.7)),
                db=self.db,
                tenant_id=self.ctx.tenant_id,
            )
            await hooks.run(
                HookTrigger.AFTER_REASONING,
                HookScope.AGENT,
                agent_id,
                {"module": SCAN_MODULE_AGENT_CHAT, "agent_id": str(agent_id), "text": answer[:500]},
            )
            return ChatResponse(answer=answer, sources=[])

        return ChatResponse(
            answer="当前智能体未配置大模型。请在「模型供应商」中配置并关联，或绑定知识库/流程后使用。",
            sources=[],
        )

    async def rag_chat(
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

        - 无 ``kb_ids``：可选 tool calling，否则直连
        - 有 KB + 大模型：LangGraph 或 ``rag_answer``
        - 有 KB 无大模型：仅检索摘要
        """
        if not kb_ids:
            if (agent.config or {}).get("enable_tool_calling") and agent.model_config_id:
                from app.integrations.langchain.tool_agent import run_tool_calling_chat

                base = await self.resolve_system_prompt(agent)
                return await run_tool_calling_chat(
                    self.db,
                    self.ctx,
                    agent,
                    body,
                    agent_id=agent_id,
                    system_prompt=base,
                )
            return await self.direct_chat(agent, body, agent_id, hooks)

        if should_use_skill_tools_with_kb(agent, kb_ids):
            from app.integrations.langchain.tool_agent import run_tool_calling_chat

            base = await self.resolve_system_prompt(agent)
            cfg = agent.config if isinstance(agent.config, dict) else {}
            kb_hint = (
                "\n【知识库】请使用 knowledge_search 工具检索；"
                f"可用 kb_id：{', '.join(kb_ids)}"
            )
            if cfg.get("enable_generative_tools"):
                kb_hint += (
                    "\n【生成】可按需调用 generate_image / generate_video；"
                    "生视频耗时长且默认需用户确认。"
                )
            return await run_tool_calling_chat(
                self.db,
                self.ctx,
                agent,
                body,
                agent_id=agent_id,
                system_prompt=f"{base}{kb_hint}",
            )

        base = await self.resolve_system_prompt(agent)

        if agent.model_config_id and agent.model_config:
            before = await hooks.run(
                HookTrigger.BEFORE_REASONING,
                HookScope.AGENT,
                agent_id,
                {
                    "module": SCAN_MODULE_AGENT_CHAT,
                    "agent_id": str(agent_id),
                    "mode": "rag",
                    "query": body.query,
                    "query_preview": body.query[:200],
                },
            )
            reasoning_query = str(before.payload.get("query", body.query))
            retrieve_query = reasoning_query.strip() or body.query.strip()
            if not retrieve_query and body.media:
                retrieve_query = "用户附图提问"
            chat_query, _ = await self.resolve_chat_media_parts(agent, body)
            prompt_query = reasoning_query.strip() or chat_query
            temperature = float((agent.config or {}).get("temperature", 0.7))
            if should_use_langgraph_rag(agent, kb_ids=kb_ids):
                answer, all_hits, steps = await run_rag_workflow(
                    model=agent.model_config,
                    system_prompt=base,
                    query=retrieve_query,
                    prompt_query=prompt_query,
                    kb_ids=kb_ids,
                    tenant_id=agent.tenant_id,
                    agent_id=agent_id,
                    top_k=top_k,
                    temperature=temperature,
                    agent_config=agent.config or {},
                    conversation_id=body.conversation_id,
                    media=body.media or None,
                    user_id=self.ctx.user_id,
                )
            else:
                answer, all_hits = await rag_answer(
                    model=agent.model_config,
                    system_prompt=base,
                    query=prompt_query,
                    kb_ids=kb_ids,
                    tenant_id=agent.tenant_id,
                    db=self.db,
                    top_k=top_k,
                    temperature=temperature,
                    media=body.media or None,
                    ctx=self.ctx,
                    retrieve_query=retrieve_query,
                )
                steps = [{"type": "rag_linear", "engine": "langchain"}]
            await hooks.run(
                HookTrigger.AFTER_REASONING,
                HookScope.AGENT,
                agent_id,
                {"module": SCAN_MODULE_AGENT_CHAT, "agent_id": str(agent_id), "text": answer[:500]},
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
