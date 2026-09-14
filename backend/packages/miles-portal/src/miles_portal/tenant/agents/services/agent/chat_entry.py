"""租户侧对话入口与子智能体工位。"""

from __future__ import annotations

from uuid import UUID

from miles_ai.flow_runtime.runtime_factory import get_flow_runtime
from miles_ai.integrations.generative.image.prompt_guard import user_requests_image_collage
from miles_ai.integrations.generative.request_prefs import (
    clear_generative_request_prefs,
    set_generative_request_prefs,
)
from miles_ai.integrations.langchain.chat_models import OnDelta
from miles_common.exceptions import BadRequestError
from miles_core.logging import get_logger
from miles_core.models.agent import Agent, AgentStatus, AgentType
from miles_portal.tenant.a2a.services.peer_refs import list_agent_a2a_peer_refs
from miles_portal.tenant.agents.schemas.agent import ChatRequest, ChatResponse
from miles_portal.tenant.agents.services.call_records import ChatCallRecorder
from miles_portal.tenant.agents.services.sub_agents import list_sub_agent_bindings
from miles_portal.tenant.compliance.constants import SCAN_MODULE_AGENT_CHAT
from miles_portal.tenant.compliance.services.compliance import ComplianceService
from miles_portal.tenant.hooks.models import HookScope, HookTrigger
from miles_portal.tenant.hooks.services.runner import HookRunner
from miles_portal.tenant.models.services.usage import begin_chat_usage_accumulation, end_chat_usage_accumulation

logger = get_logger(__name__)


class AgentChatEntryMixin:
    """``chat`` / ``chat_as_child`` 入口；依赖 Turn / Rag Mixin 收尾与 RAG。"""

    async def chat(
        self,
        agent_id: UUID,
        body: ChatRequest,
        *,
        on_delta: OnDelta | None = None,
    ) -> ChatResponse:
        """租户侧智能体对话入口：合规与 Hook 包裹整条调用链。

        按 a2a_host / subagent / a2a_augmented / flow / rag 五条路由分发；每条路由
        都经 ``finish`` → ``_complete_chat_turn`` 做出站合规、AFTER_CALL Hook 与
        调用记录收尾。异常统一走 ``recorder.record_failure`` + ON_ERROR Hook 后重抛。
        """
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
        recorder = ChatCallRecorder(
            self.db,
            self.ctx,
            agent_id=agent_id,
            body=body,
            user_query=effective_query,
            media_count=len(body.media),
        )
        route = "unknown"
        usage_acc = begin_chat_usage_accumulation()
        set_generative_request_prefs(
            image_n=body.generative_image_n,
            allow_collage=user_requests_image_collage(body.query),
            video_duration=body.generative_video_duration,
        )

        async def finish(selected_route: str, response: ChatResponse) -> ChatResponse:
            """按本次命中的路由完成收尾。

            recorder / compliance / hooks / agent_id / hook_payload 对五条路由都相同，
            故在此固化；调用处只需给出路由名与该路由的响应。
            """
            return await self._complete_chat_turn(
                recorder,
                selected_route,
                compliance=compliance,
                hooks=hooks,
                agent_id=agent_id,
                hook_payload=hook_payload,
                response=response,
            )

        try:
            before_call = await hooks.run(
                HookTrigger.BEFORE_CALL,
                HookScope.AGENT,
                agent_id,
                {**hook_payload, "direction": "in"},
            )
            hook_payload = before_call.payload
            query = str(hook_payload.get("query", effective_query))
            chat_body = body.model_copy(update={"query": query}) if query != effective_query else body
            await compliance.check_input(query, module=SCAN_MODULE_AGENT_CHAT)

            # KB / top_k 对 a2a_augmented、flow、rag 三条路由相同，提前算一次
            kb_ids = [str(kb.id) for kb in agent.knowledge_bases]
            top_k = int((agent.config or {}).get("top_k", 5))

            if agent.agent_type == AgentType.A2A:
                from miles_portal.tenant.a2a.invoke import run_a2a_host_chat

                route = "a2a_host"
                return await finish(route, await run_a2a_host_chat(self, agent, chat_body))

            bindings = await list_sub_agent_bindings(self.db, agent_id)
            peer_refs = await list_agent_a2a_peer_refs(self.db, agent_id)
            if bindings:
                from miles_ai.integrations.deepagents.io import ParentChatInput
                from miles_ai.integrations.deepagents.orchestrator import run_subagent_planned_chat

                route = "subagent"
                result = await run_subagent_planned_chat(
                    self,
                    agent,
                    bindings,
                    ParentChatInput(
                        query=chat_body.query,
                        inputs=chat_body.inputs,
                        conversation_id=chat_body.conversation_id,
                    ),
                )
                response = ChatResponse(answer=result.answer, sources=[], steps=result.steps)
                if peer_refs:
                    response = await self.maybe_augment_a2a(agent, chat_body, response)
                return await finish(route, response)

            if peer_refs:
                from miles_portal.tenant.a2a.invoke import run_a2a_augmented_chat

                route = "a2a_augmented"
                response = await run_a2a_augmented_chat(
                    self,
                    agent,
                    chat_body,
                    kb_ids=kb_ids,
                    top_k=top_k,
                    agent_id=agent_id,
                    hooks=hooks,
                )
                return await finish(route, response)

            response = await self._run_published_flow(agent, agent_id, chat_body, query=query, kb_ids=kb_ids)
            route = "flow" if response is not None else self._resolve_rag_route(agent, kb_ids)
            if response is None:
                response = await self.rag_chat(agent, chat_body, kb_ids, top_k, agent_id, hooks, on_delta=on_delta)
            response = await self.maybe_augment_a2a(agent, chat_body, response)
            return await finish(route, response)
        except Exception as exc:
            await recorder.record_failure(exc, route=route)
            await hooks.run(
                HookTrigger.ON_ERROR,
                HookScope.AGENT,
                agent_id,
                {**hook_payload, "error": str(exc)},
            )
            # 失败审计必须自己落库：两个出口（``get_db`` 的 except 与 WS 侧
            # ``_run_chat_turn`` 的 except）在异常时一律 rollback，会把刚 flush 的
            # 调用记录与 ON_ERROR 日志一起撤销——于是 AgentChatCall 只会有 success
            # 行，failed/blocked 永远查不到；出站合规拦截也就失去了留痕。
            # commit 失败不能再掩盖原始异常，故只记日志后继续抛出 exc。
            try:
                await self.db.commit()
            except Exception:
                logger.exception("失败调用记录落库失败 agent_id=%s", agent_id)
            raise
        finally:
            clear_generative_request_prefs()
            end_chat_usage_accumulation(usage_acc)

    async def _run_published_flow(
        self,
        agent: Agent,
        agent_id: UUID,
        body: ChatRequest,
        *,
        query: str,
        kb_ids: list[str],
    ) -> ChatResponse | None:
        """绑定了已发布流程则执行并返回响应，否则返回 ``None`` 交调用方兜底。

        ``query`` 单独传入而不从 ``body`` 取：主入口会先经 BEFORE_CALL Hook 改写
        query，子智能体工位则用原样 query，两者输入不同但执行流程一致。
        """
        if not agent.published_flow_id:
            return None
        flow = await self.flow_repo.get_by_id(agent.published_flow_id)
        if not flow or flow.current_version <= 0:
            return None
        version = await self.flow_repo.get_version(flow.id, flow.current_version)
        if not version:
            return None

        inputs = {"query": query, **body.inputs}
        if not str(inputs.get("query", "")).strip() and body.media:
            inputs["query"] = "请根据附图回答。"
        ctx = await self.flow_run_context(
            agent,
            agent_id=agent_id,
            inputs=inputs,
            kb_ids=kb_ids,
            media=body.media,
        )
        result = await get_flow_runtime().run(version.graph_json, ctx)
        return ChatResponse(answer=str(result.output), steps=result.steps)

    async def chat_as_child_simple(
        self,
        child_id: UUID,
        *,
        query: str,
        inputs: dict | None = None,
    ) -> ChatResponse:
        """子智能体工位简化入口：免构造 ``ChatRequest``（供 L3 deepagents 契约调用）。"""
        return await self.chat_as_child(
            child_id,
            ChatRequest(query=query, inputs=inputs or {}),
        )

    async def chat_as_child(self, child_id: UUID, body: ChatRequest) -> ChatResponse:
        """子智能体工位：不再走子智能体规划，仅 RAG/流程/直连。"""
        child = await self.get_agent_or_raise(child_id)
        if child.status != AgentStatus.ENABLED:
            raise BadRequestError("子智能体已禁用")
        kb_ids = [str(kb.id) for kb in child.knowledge_bases]
        top_k = int((child.config or {}).get("top_k", 5))
        hooks = HookRunner(self.db, self.ctx.tenant_id)

        if child.published_flow_id:
            flow_response = await self._run_published_flow(child, child_id, body, query=body.query, kb_ids=kb_ids)
            if flow_response is not None:
                return flow_response

        return await self.rag_chat(child, body, kb_ids, top_k, child_id, hooks)
