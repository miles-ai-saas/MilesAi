"""直连 LLM、tool_agent 装配与 A2A 增强。"""

from __future__ import annotations

from uuid import UUID

from miles_core.models.agent import Agent
from miles_integrations.chat.multimodal import build_user_message, resolve_media_refs
from miles_integrations.generative.image.prompt_guard import user_requests_image_collage
from miles_integrations.langchain.chat_models import OnDelta, ainvoke_chat
from miles_portal.tenant.a2a.services.peer_refs import list_agent_a2a_peer_refs
from miles_portal.tenant.agents.schemas.agent import ChatRequest, ChatResponse
from miles_portal.tenant.agents.services.agent.chat_hints import (
    _generative_tools_system_hint,
    _knowledge_tools_system_hint,
)
from miles_portal.tenant.agents.services.chat_memory import load_chat_history_messages
from miles_portal.tenant.agents.services.user_memory import UserMemoryService
from miles_portal.tenant.attachments.services.media_reader import build_flow_media_reader
from miles_portal.tenant.compliance.constants import SCAN_MODULE_AGENT_CHAT
from miles_portal.tenant.hooks.models import HookScope, HookTrigger
from miles_portal.tenant.hooks.services.runner import HookRunner


class AgentChatDirectMixin:
    """无 KB 直连、tool_agent 路径与 A2A peer 增强。"""

    async def maybe_augment_a2a(self, agent: Agent, body: ChatRequest, response: ChatResponse) -> ChatResponse:
        """若配置了 A2A peer，在已有回答上追加外部智能体增强。"""
        refs = await list_agent_a2a_peer_refs(self.db, agent.id)
        if not refs:
            return response
        from miles_portal.tenant.a2a.invoke import augment_response_with_a2a

        return await augment_response_with_a2a(self, agent, body, response)

    async def resolve_chat_media_parts(self, agent: Agent, body: ChatRequest) -> tuple[str, list]:
        """解析附图，返回生成用 query 文本与 multimodal content parts。

        用短会话读取器：本方法只读对象存储，不该借用请求会话——否则对象存储 I/O
        期间请求事务一直开着（两条 RAG 路径与直连路径都会调用本方法）。
        """
        max_media = int((agent.config or {}).get("max_media_per_turn", 10))
        parts: list = []
        if body.media:
            parts = await resolve_media_refs(
                build_flow_media_reader(tenant_id=self.ctx.tenant_id, user_id=self.ctx.user_id),
                body.media,
                max_count=max_media,
            )
        query = body.query.strip() or ("请根据附图回答。" if parts else body.query.strip())
        return query, parts

    async def direct_chat(
        self,
        agent: Agent,
        body: ChatRequest,
        agent_id: UUID,
        hooks: HookRunner,
        *,
        on_delta: OnDelta | None = None,
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
            body_media_count = len(body.media) if body.media else 0
            user_msg = build_user_message(query=reasoning_query, media_parts=media_parts)
            history = await load_chat_history_messages(
                self.db,
                tenant_id=self.ctx.tenant_id,
                agent_id=agent_id,
                conversation_id=body.conversation_id,
            )
            memory_rows, long_term = await UserMemoryService(self.db, self.ctx).load_for_inject(
                agent=agent,
                user_id=self.ctx.user_id,
                query=reasoning_query,
            )
            system_content = f"{base}{long_term}"
            model = await self.resolve_invoke_model(agent.model_config)
            usage_sink = self.chat_usage_sink(model, source_id=agent_id)
            # 释放请求事务：模型解析会读租户凭据，随后是单次 LLM 调用，中间无需本会话。
            await self.db.commit()
            answer = await ainvoke_chat(
                model,
                [
                    {"role": "system", "content": system_content},
                    *history,
                    user_msg,
                ],
                temperature=float((agent.config or {}).get("temperature", 0.7)),
                usage_sink=usage_sink,
                on_delta=on_delta,
            )
            await hooks.run(
                HookTrigger.AFTER_REASONING,
                HookScope.AGENT,
                agent_id,
                {"module": SCAN_MODULE_AGENT_CHAT, "agent_id": str(agent_id), "text": answer[:500]},
            )
            steps: list[dict] = [
                {
                    "type": "direct_chat",
                    "media_count": body_media_count,
                    "media_resolved": len(media_parts),
                    "model_type": agent.model_config.model_type,
                    "history_messages": len(history),
                }
            ]
            if long_term:
                steps.append({"type": "user_memory", "items": len(memory_rows), "chars": len(long_term)})
            if body_media_count > 0 and agent.model_config.model_type != "vision" and media_parts:
                steps.append({"type": "multimodal_warning", "message": f"当前模型类型为 {agent.model_config.model_type}（非 vision），图片可能无法被模型识别"})
            return ChatResponse(answer=answer, sources=[], steps=steps)

        return ChatResponse(
            answer="当前智能体未配置大模型。请在「模型供应商」中配置并关联，或绑定知识库/流程后使用。",
            sources=[],
        )

    async def _run_tool_agent(
        self,
        agent: Agent,
        body: ChatRequest,
        *,
        agent_id: UUID,
        system_prompt: str,
        kb_ids: list[str] | None = None,
        kb_top_k: int | None = None,
        on_delta: OnDelta | None = None,
    ) -> ChatResponse:
        """装配并运行 tool_agent（RAG 与 tool calling 共存路径）。

        注入运行时默认值到 ``agent.config``：输入区生图/时长偏好、会话 id，
        以及在绑定 KB 时注入 ``_bound_kb_ids`` / ``_bound_kb_top_k``，
        供 ``knowledge_search`` 省略 kb 与条数参数时回退。
        ``on_delta`` 透传至 ``run_tool_calling_chat``，供 WS/A2A 最终回答真 token 流式。
        """
        from miles_integrations.langchain.tool_agent import run_tool_calling_chat
        from miles_portal.tenant.tools.services.agent_executor import (
            build_short_session_agent_tool_executor,
        )
        from miles_portal.tenant.tools.services.agent_tool_assembly import assemble_agent_tools

        cfg = agent.config if isinstance(agent.config, dict) else {}
        hint = _knowledge_tools_system_hint(list(kb_ids)) if kb_ids else ""
        if cfg.get("enable_generative_tools"):
            hint += _generative_tools_system_hint(
                image_n=body.generative_image_n,
                video_duration=body.generative_video_duration,
            )

        from miles_portal.tenant.agents.services.agent_limits import resolve_max_tool_iterations

        agent_config_with_defaults = dict(cfg)
        agent_config_with_defaults["max_tool_iterations"] = resolve_max_tool_iterations(agent_config_with_defaults)
        if body.conversation_id:
            agent_config_with_defaults["_conversation_id"] = body.conversation_id
        # 始终注入输入区张数（含 1），供 generate_image 强制覆盖 LLM 的 n
        agent_config_with_defaults["_generative_image_n"] = body.generative_image_n
        agent_config_with_defaults["_image_allow_collage"] = user_requests_image_collage(body.query)
        if body.generative_video_duration != 5:
            agent_config_with_defaults["_generative_video_duration"] = body.generative_video_duration
        if kb_ids:
            agent_config_with_defaults["_bound_kb_ids"] = [str(i) for i in kb_ids]
            if kb_top_k:
                agent_config_with_defaults["_bound_kb_top_k"] = int(kb_top_k)
        agent.config = agent_config_with_defaults

        model = await self.resolve_invoke_model(agent.model_config)
        usage_sink = self.chat_usage_sink(model, source_id=agent_id)
        platform_tools = await assemble_agent_tools(self.db, self.ctx, agent.config or {})
        history = await load_chat_history_messages(
            self.db,
            tenant_id=self.ctx.tenant_id,
            agent_id=agent_id,
            conversation_id=body.conversation_id,
        )
        _, long_term = await UserMemoryService(self.db, self.ctx).load_for_inject(
            agent=agent,
            user_id=self.ctx.user_id,
            query=body.query,
        )
        # assemble 仍需 agent 附着会话；之后 expunge，避免 ephemeral config 被 commit flush 入库
        self.db.expunge(agent)
        await self.db.commit()  # 释放请求会话；后续 LLM/工具用短会话
        tool_executor = build_short_session_agent_tool_executor(
            self.ctx,
            agent_id=agent_id,
            actor_user_id=self.ctx.user_id,
            invoke_source="agent",
            agent_config=agent_config_with_defaults,
        )
        return await run_tool_calling_chat(
            agent,
            body,
            system_prompt=f"{system_prompt}{hint}{long_term}",
            model=model,
            usage_sink=usage_sink,
            platform_tools=platform_tools,
            tool_executor=tool_executor,
            media_reader=build_flow_media_reader(
                tenant_id=self.ctx.tenant_id, user_id=self.ctx.user_id
            ),
            kb_ids=list(kb_ids) if kb_ids else None,
            history_messages=history,
            on_delta=on_delta,
        )
