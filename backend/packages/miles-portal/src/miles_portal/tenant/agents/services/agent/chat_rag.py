"""RAG / 流程 RunContext；组合 ``AgentChatDirectMixin``。

``rag_chat`` 保留在本模块，便于单测 ``monkeypatch.setattr(chat_rag_mod, …)``。
"""

from __future__ import annotations

from uuid import UUID

from miles_ai.flow_runtime.types import RunContext
from miles_ai.rag.generate import build_rag_prompt, format_hits_context, generate_rag_answer, retrieve_hits
from miles_ai.rag.graph.runner import run_rag_workflow, should_use_langgraph_rag
from miles_core.infra.db import AsyncSessionLocal
from miles_core.models.agent import Agent
from miles_core.models.model import ModelConfig
from miles_integrations.langchain.chat_models import OnDelta
from miles_portal.tenant.agents.schemas.agent import ChatRequest, ChatResponse
from miles_portal.tenant.agents.services.agent.chat_direct import AgentChatDirectMixin
from miles_portal.tenant.agents.services.agent.serialization import should_use_tools_with_kb
from miles_portal.tenant.agents.services.chat_memory import (
    format_history_block,
    load_chat_history_messages,
)
from miles_portal.tenant.agents.services.user_memory import UserMemoryService
from miles_portal.tenant.attachments.services.media_reader import build_flow_media_reader
from miles_portal.tenant.compliance.constants import SCAN_MODULE_AGENT_CHAT
from miles_portal.tenant.flows.repositories.flow import FlowRepository
from miles_portal.tenant.flows.services.run_context import make_flow_model_resolver
from miles_portal.tenant.generative.services.job import GenerativeJobService
from miles_portal.tenant.generative.services.job_execution import (
    submit_generative_image_job,
    submit_generative_video_job,
)
from miles_portal.tenant.hooks.models import HookScope, HookTrigger
from miles_portal.tenant.hooks.services.runner import HookRunner
from miles_portal.tenant.kb.services.embeddings import build_kb_retrieval_bindings
from miles_portal.tenant.models.services.generative_model_resolve import (
    resolve_image_gen_model,
    resolve_video_gen_model,
)
from miles_portal.tenant.models.services.model_resolve import resolve_model_for_invoke
from miles_portal.tenant.models.services.usage import ChatUsageSink, make_flow_usage_sink_factory


class AgentChatRagMixin(AgentChatDirectMixin):
    """RAG 与直连对话；依赖 ``AgentCrudMixin`` 的 prompt 解析。"""

    flow_repo: FlowRepository

    async def flow_run_context(
        self,
        agent: Agent,
        *,
        agent_id: UUID,
        inputs: dict,
        kb_ids: list[str],
        media: list | None = None,
        on_delta: OnDelta | None = None,
    ) -> RunContext:
        """构造流程画布 ``RunContext``（含 system_prompt、KB、附图 payload）。

        ``on_delta`` 由对话 WS/A2A 注入，供答案产出 LLMCall 真 token 流式。
        """
        from miles_portal.tenant.compliance.services.scan_words_loader import build_scan_words_loader
        from miles_portal.tenant.flows.services.subflow_loader import build_subflow_graph_loader
        from miles_portal.tenant.generative.services.orchestration import (
            generate_image_for_model,
            generate_video_for_model,
        )
        from miles_portal.tenant.prompts.services.template_loader import build_prompt_template_loader
        from miles_portal.tenant.tools.services.flow_invoker import build_flow_tool_invoker

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
            resolve_model=make_flow_model_resolver(agent.tenant_id),
            usage_sink_factory=make_flow_usage_sink_factory(agent.tenant_id, source_id=agent_id),
            kb_retrieval=build_kb_retrieval_bindings(),
            resolve_generative_image=resolve_image_gen_model,
            resolve_generative_video=resolve_video_gen_model,
            # settings generative_*_async 关闭时不注入 ⇒ 节点落同步 resolver 兜底（不产生生成任务）
            submit_generative_image=submit_generative_image_job if GenerativeJobService.image_async_enabled() else None,
            submit_generative_video=submit_generative_video_job if GenerativeJobService.video_async_enabled() else None,
            invoke_platform_tool=build_flow_tool_invoker(),
            resolve_prompt_template=build_prompt_template_loader(),
            load_scan_words=build_scan_words_loader(),
            load_subflow_graph=build_subflow_graph_loader(),
            media_reader=build_flow_media_reader(tenant_id=str(self.ctx.tenant_id), user_id=self.ctx.user_id),
            generate_image_sync=generate_image_for_model,
            generate_video_sync=generate_video_for_model,
            on_delta=on_delta,
        )

    async def rag_chat(
        self,
        agent: Agent,
        body: ChatRequest,
        kb_ids: list[str],
        top_k: int,
        agent_id: UUID,
        hooks: HookRunner,
        *,
        on_delta: OnDelta | None = None,
    ) -> ChatResponse:
        """
        知识库增强对话。

        - 无 ``kb_ids``：可选 tool calling，否则直连
        - 有 KB + 大模型：LangGraph 或线性 ``generate_rag_answer``
        - 有 KB 无大模型：仅检索摘要
        """
        kb_bindings = build_kb_retrieval_bindings()
        if not kb_ids:
            cfg = agent.config if isinstance(agent.config, dict) else {}
            if (cfg.get("enable_tool_calling") or cfg.get("enable_generative_tools")) and agent.model_config_id:
                base = await self.resolve_system_prompt(agent)
                return await self._run_tool_agent(
                    agent, body, agent_id=agent_id, system_prompt=base, on_delta=on_delta
                )
            return await self.direct_chat(agent, body, agent_id, hooks, on_delta=on_delta)

        if should_use_tools_with_kb(agent, kb_ids):
            base = await self.resolve_system_prompt(agent)
            return await self._run_tool_agent(
                agent,
                body,
                agent_id=agent_id,
                system_prompt=base,
                kb_ids=kb_ids,
                kb_top_k=top_k,
                on_delta=on_delta,
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
            history = await load_chat_history_messages(
                self.db,
                tenant_id=self.ctx.tenant_id,
                agent_id=agent_id,
                conversation_id=body.conversation_id,
            )
            memory_rows, long_term = await UserMemoryService(self.db, self.ctx).load_for_inject(
                agent=agent,
                user_id=self.ctx.user_id,
                query=prompt_query or retrieve_query,
            )
            # 长期 → 近期；检索仍用本轮 retrieve_query
            gen_system = f"{base}{long_term}{format_history_block(history)}"
            model = await self.resolve_invoke_model(agent.model_config)
            usage_sink = self.chat_usage_sink(model, source_id=agent_id)
            if should_use_langgraph_rag(agent, kb_ids=kb_ids):
                # 释放请求事务：检索由 retrieve 节点自开短会话完成，生成阶段不再需要本会话。
                await self.db.commit()
                answer, all_hits, steps = await run_rag_workflow(
                    model=model,
                    system_prompt=gen_system,
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
                    on_delta=on_delta,
                    usage_sink=usage_sink,
                    bindings=kb_bindings,
                    media_reader=build_flow_media_reader(tenant_id=self.ctx.tenant_id, user_id=self.ctx.user_id),
                )
                steps = [
                    *list(steps or []),
                    {"type": "chat_memory", "history_messages": len(history)},
                ]
            else:
                # 检索必须在 L1 用短会话完成，否则它会在生成入口内部重新打开请求事务，
                # 使「生成期间不占连接」失效。retrieve_query 用于检索、prompt_query 写入 prompt。
                # 检索短会话每调用新开（AsyncSessionLocal，engine 按事件循环持有）：
                # 本路径在 Celery（每次 asyncio.run 新 loop）内同样可达，且与调用方事务无关。
                search_q = (retrieve_query if retrieve_query is not None else prompt_query).strip()
                async with AsyncSessionLocal() as search_db:
                    linear_hits = await retrieve_hits(
                        search_q,
                        tenant_id=agent.tenant_id,
                        kb_ids=kb_ids,
                        db=search_db,
                        top_k=top_k,
                        bindings=kb_bindings,
                    )
                await self.db.commit()
                prompt = build_rag_prompt(system_prompt=gen_system, query=prompt_query, hits=linear_hits)
                answer = await generate_rag_answer(
                    model=model,
                    prompt=prompt,
                    media=body.media or None,
                    media_reader=build_flow_media_reader(tenant_id=self.ctx.tenant_id, user_id=self.ctx.user_id),
                    temperature=temperature,
                    on_delta=on_delta,
                    usage_sink=usage_sink,
                )
                all_hits = linear_hits
                steps = [
                    {
                        "type": "rag_linear",
                        "engine": "langchain",
                        "history_messages": len(history),
                    }
                ]
            await hooks.run(
                HookTrigger.AFTER_REASONING,
                HookScope.AGENT,
                agent_id,
                {"module": SCAN_MODULE_AGENT_CHAT, "agent_id": str(agent_id), "text": answer[:500]},
            )
            if long_term:
                steps = [*list(steps or []), {"type": "user_memory", "items": len(memory_rows), "chars": len(long_term)}]
        else:
            all_hits = await retrieve_hits(
                body.query,
                tenant_id=agent.tenant_id,
                kb_ids=kb_ids,
                db=self.db,
                top_k=top_k,
                bindings=kb_bindings,
            )
            answer = f"（未配置大模型，以下为检索摘要）\n\n{format_hits_context(all_hits)}"
            steps = []

        return ChatResponse(answer=answer, sources=all_hits, steps=steps)

    async def resolve_invoke_model(self, model: ModelConfig | None) -> ModelConfig:
        """按当前租户解析可用模型（合并 BYOK）；无模型时抛 ValueError。"""
        if model is None:
            raise ValueError("未配置可用模型")
        return await resolve_model_for_invoke(self.db, model, self.ctx.tenant_id)

    def chat_usage_sink(
        self,
        model: ModelConfig,
        *,
        source_id: UUID | None = None,
    ) -> ChatUsageSink:
        """构造注入引擎的用量记录器（chat 累计 + 落库）。"""
        return ChatUsageSink(
            tenant_id=self.ctx.tenant_id,
            model=model,
            source_id=source_id,
        )
