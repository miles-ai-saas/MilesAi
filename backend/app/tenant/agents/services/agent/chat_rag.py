"""RAG / 直连 / tool calling 与流程 RunContext、多模态解析。"""

from __future__ import annotations

from uuid import UUID

from app.flow_runtime.types import RunContext
from app.integrations.chat.multimodal import build_user_message, resolve_media_refs
from app.integrations.generative.image.prompt_guard import user_requests_image_collage
from app.integrations.langchain.chat_models import OnDelta, ainvoke_chat
from app.integrations.langgraph.runner import run_rag_workflow, should_use_langgraph_rag
from app.models.agent import Agent
from app.models.model import ModelConfig
from app.rag.generate import format_hits_context, rag_answer, retrieve_hits
from app.tenant.a2a.services.peer_refs import list_agent_a2a_peer_refs
from app.tenant.agents.schemas.agent import ChatRequest, ChatResponse
from app.tenant.agents.services.agent.serialization import should_use_skill_tools_with_kb
from app.tenant.compliance.constants import SCAN_MODULE_AGENT_CHAT
from app.tenant.flows.repositories.flow import FlowRepository
from app.tenant.flows.services.run_context import make_flow_model_resolver
from app.tenant.generative.services.job import GenerativeJobService
from app.tenant.generative.services.job_execution import (
    submit_generative_image_job,
    submit_generative_video_job,
)
from app.tenant.hooks.models import HookScope, HookTrigger
from app.tenant.hooks.services.runner import HookRunner
from app.tenant.kb.services.embeddings import build_kb_retrieval_bindings
from app.tenant.models.services.generative_model_resolve import (
    resolve_image_gen_model,
    resolve_video_gen_model,
)
from app.tenant.models.services.model_resolve import resolve_model_for_invoke
from app.tenant.models.services.usage import ChatUsageSink


def _generative_tools_system_hint(*, image_n: int = 1, video_duration: int = 5) -> str:
    """按配置注入的生图/生视频协议；业务 system prompt 不应再手写 tool_call 规则。

    张数以用户输入区为准，由平台在 tool 入参层强制覆盖；模型不得在正文自行「确认」或改写 n。
    """
    dur_hint = (
        f"\n若用户要求生成视频：调用 generate_video；duration 取用户输入区当前值 {video_duration}。"
        if video_duration != 5
        else "\n若用户要求生成视频：调用 generate_video；duration 以用户输入为准。"
    )
    return (
        "\n【生成工具·平台协议】"
        "\n你已挂载 generate_image（以及可用时的 generate_video）。"
        "\n当用户要求生成图片时：必须通过 function calling 发起真正的 tool_call，"
        "把画面描述写入参数 prompt；禁止在回复正文输出生图提示词、JSON、代码块或伪调用。"
        "\n出图数量由输入区控件决定，不可改写："
        f"本次 n={image_n}，调用 generate_image 时必须传 n={image_n}；"
        "禁止根据业务习惯、多视角、参考图数量自行改为其他 n；"
        "禁止在回复正文写「已确认 n=…」或自行宣布张数。"
        "\nsize 仅在用户明确要求时填写，否则可省略（用模型默认）。"
        "\nn>1 表示生成多张彼此独立的完整单图（每张一个主体画面），"
        "禁止在 prompt 里写四宫格/九宫格/分镜拼贴/组图拼接；"
        "除非用户本轮明确要求组图、拼贴或宫格布局。"
        "\n注意：尺寸单边 ≥1280 或 n≥3 需用户二次确认；确认前勿重复调用。"
        "\n同一轮用户消息仅允许调用一次 generate_image / generate_video。"
        f"{dur_hint}"
    )


class AgentChatRagMixin:
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
            resolve_model=make_flow_model_resolver(agent.tenant_id),
            usage_sink=None,
            kb_retrieval=build_kb_retrieval_bindings(),
            resolve_generative_image=resolve_image_gen_model,
            resolve_generative_video=resolve_video_gen_model,
            # settings generative_*_async 关闭时不注入 ⇒ 节点落同步 resolver 兜底（不产生生成任务）
            submit_generative_image=submit_generative_image_job if GenerativeJobService.image_async_enabled() else None,
            submit_generative_video=submit_generative_video_job if GenerativeJobService.video_async_enabled() else None,
        )

    async def maybe_augment_a2a(self, agent: Agent, body: ChatRequest, response: ChatResponse) -> ChatResponse:
        """若配置了 A2A peer，在已有回答上追加外部智能体增强。"""
        refs = await list_agent_a2a_peer_refs(self.db, agent.id)
        if not refs:
            return response
        from app.tenant.a2a.invoke import augment_response_with_a2a

        return await augment_response_with_a2a(self, agent, body, response)

    async def resolve_chat_media_parts(self, agent: Agent, body: ChatRequest) -> tuple[str, list]:
        """解析附图，返回生成用 query 文本与 multimodal content parts。"""
        max_media = int((agent.config or {}).get("max_media_per_turn", 10))
        parts: list = []
        if body.media:
            parts = await resolve_media_refs(self.db, self.ctx, body.media, max_count=max_media)
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
            model = await self.resolve_invoke_model(agent.model_config)
            usage_sink = self.chat_usage_sink(model, source_id=agent_id)
            answer = await ainvoke_chat(
                model,
                [
                    {"role": "system", "content": base},
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
                {"type": "direct_chat", "media_count": body_media_count, "media_resolved": len(media_parts), "model_type": agent.model_config.model_type}
            ]
            if body_media_count > 0 and agent.model_config.model_type != "vision" and media_parts:
                steps.append({"type": "multimodal_warning", "message": f"当前模型类型为 {agent.model_config.model_type}（非 vision），图片可能无法被模型识别"})
            return ChatResponse(answer=answer, sources=[], steps=steps)

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
        *,
        on_delta: OnDelta | None = None,
    ) -> ChatResponse:
        """
        知识库增强对话。

        - 无 ``kb_ids``：可选 tool calling，否则直连
        - 有 KB + 大模型：LangGraph 或 ``rag_answer``
        - 有 KB 无大模型：仅检索摘要
        """
        kb_bindings = build_kb_retrieval_bindings()
        if not kb_ids:
            cfg = agent.config if isinstance(agent.config, dict) else {}
            if (cfg.get("enable_tool_calling") or cfg.get("enable_generative_tools")) and agent.model_config_id:
                from app.integrations.langchain.tool_agent import run_tool_calling_chat

                base = await self.resolve_system_prompt(agent)
                kb_hint = ""
                if cfg.get("enable_generative_tools"):
                    kb_hint = _generative_tools_system_hint(
                        image_n=body.generative_image_n,
                        video_duration=body.generative_video_duration,
                    )
                # 将输入区参数注入 agent.config，供 handle_generate_image / handle_generate_video
                # 在 LLM 未传 n/duration 时作为实际默认值使用
                agent_config_with_defaults = dict(cfg)
                if body.conversation_id:
                    agent_config_with_defaults["_conversation_id"] = body.conversation_id
                # 始终注入输入区张数（含 1），供 generate_image 强制覆盖 LLM 的 n
                agent_config_with_defaults["_generative_image_n"] = body.generative_image_n
                agent_config_with_defaults["_image_allow_collage"] = user_requests_image_collage(body.query)
                if body.generative_video_duration != 5:
                    agent_config_with_defaults["_generative_video_duration"] = body.generative_video_duration
                agent.config = agent_config_with_defaults
                model = await self.resolve_invoke_model(agent.model_config)
                usage_sink = self.chat_usage_sink(model, source_id=agent_id)
                return await run_tool_calling_chat(
                    self.db,
                    self.ctx,
                    agent,
                    body,
                    agent_id=agent_id,
                    system_prompt=f"{base}{kb_hint}",
                    model=model,
                    usage_sink=usage_sink,
                )
            return await self.direct_chat(agent, body, agent_id, hooks, on_delta=on_delta)

        if should_use_skill_tools_with_kb(agent, kb_ids):
            from app.integrations.langchain.tool_agent import run_tool_calling_chat

            base = await self.resolve_system_prompt(agent)
            cfg = agent.config if isinstance(agent.config, dict) else {}
            kb_hint = f"\n【知识库】请使用 knowledge_search 工具检索；可用 kb_id：{', '.join(kb_ids)}"
            if cfg.get("enable_generative_tools"):
                kb_hint += _generative_tools_system_hint(
                    image_n=body.generative_image_n,
                    video_duration=body.generative_video_duration,
                )
            # 将输入区参数注入 agent.config，供 handle_generate_image / handle_generate_video
            agent_config_with_defaults = dict(cfg)
            if body.conversation_id:
                agent_config_with_defaults["_conversation_id"] = body.conversation_id
            agent_config_with_defaults["_generative_image_n"] = body.generative_image_n
            agent_config_with_defaults["_image_allow_collage"] = user_requests_image_collage(body.query)
            if body.generative_video_duration != 5:
                agent_config_with_defaults["_generative_video_duration"] = body.generative_video_duration
            agent.config = agent_config_with_defaults
            model = await self.resolve_invoke_model(agent.model_config)
            usage_sink = self.chat_usage_sink(model, source_id=agent_id)
            return await run_tool_calling_chat(
                self.db,
                self.ctx,
                agent,
                body,
                agent_id=agent_id,
                system_prompt=f"{base}{kb_hint}",
                model=model,
                usage_sink=usage_sink,
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
            model = await self.resolve_invoke_model(agent.model_config)
            usage_sink = self.chat_usage_sink(model, source_id=agent_id)
            if should_use_langgraph_rag(agent, kb_ids=kb_ids):
                answer, all_hits, steps = await run_rag_workflow(
                    model=model,
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
                    on_delta=on_delta,
                    usage_sink=usage_sink,
                    bindings=kb_bindings,
                )
            else:
                answer, all_hits = await rag_answer(
                    model=model,
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
                    on_delta=on_delta,
                    usage_sink=usage_sink,
                    bindings=kb_bindings,
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
            db=self.db,
            tenant_id=self.ctx.tenant_id,
            model=model,
            source_id=source_id,
        )
