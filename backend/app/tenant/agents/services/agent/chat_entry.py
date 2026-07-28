"""租户侧对话入口与子智能体工位。"""

from __future__ import annotations

from uuid import UUID

from app.common.exceptions import BadRequestError
from app.flow_runtime.runtime_factory import get_flow_runtime
from app.integrations.generative.image.prompt_guard import user_requests_image_collage
from app.integrations.generative.request_prefs import (
    clear_generative_request_prefs,
    set_generative_request_prefs,
)
from app.models.agent import AgentStatus, AgentType
from app.tenant.a2a.services.peer_refs import list_agent_a2a_peer_refs
from app.tenant.agents.schemas.agent import ChatRequest, ChatResponse
from app.tenant.agents.services.call_records import ChatCallRecorder
from app.tenant.agents.services.sub_agents import list_sub_agent_bindings
from app.tenant.compliance.constants import SCAN_MODULE_AGENT_CHAT
from app.tenant.compliance.services.compliance import ComplianceService
from app.tenant.hooks.models import HookScope, HookTrigger
from app.tenant.hooks.services.runner import HookRunner
from app.tenant.models.services.usage import begin_chat_usage_accumulation, end_chat_usage_accumulation


class AgentChatEntryMixin:
    """``chat`` / ``chat_as_child`` 入口；依赖 Turn / Rag Mixin 收尾与 RAG。"""

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

            if agent.agent_type == AgentType.A2A:
                from app.tenant.a2a.invoke import run_a2a_host_chat

                route = "a2a_host"
                response = await run_a2a_host_chat(self, agent, chat_body)
                return await self._complete_chat_turn(
                    recorder,
                    route,
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

                route = "subagent"
                response = await run_subagent_planned_chat(self, agent, bindings, chat_body)
                if peer_refs:
                    response = await self.maybe_augment_a2a(agent, chat_body, response)
                return await self._complete_chat_turn(
                    recorder,
                    route,
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
                return await self._complete_chat_turn(
                    recorder,
                    route,
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
                        route = "flow"
                        result = await get_flow_runtime().run(version.graph_json, ctx)
                        response = ChatResponse(answer=str(result.output), steps=result.steps)
                        response = await self.maybe_augment_a2a(agent, chat_body, response)
                        return await self._complete_chat_turn(
                            recorder,
                            route,
                            compliance=compliance,
                            hooks=hooks,
                            agent_id=agent_id,
                            hook_payload=hook_payload,
                            response=response,
                        )

            route = self._resolve_rag_route(agent, kb_ids)
            response = await self.rag_chat(agent, chat_body, kb_ids, top_k, agent_id, hooks)
            response = await self.maybe_augment_a2a(agent, chat_body, response)
            return await self._complete_chat_turn(
                recorder,
                route,
                compliance=compliance,
                hooks=hooks,
                agent_id=agent_id,
                hook_payload=hook_payload,
                response=response,
            )
        except Exception as exc:
            await recorder.record_failure(exc, route=route)
            await hooks.run(
                HookTrigger.ON_ERROR,
                HookScope.AGENT,
                agent_id,
                {**hook_payload, "error": str(exc)},
            )
            raise
        finally:
            clear_generative_request_prefs()
            end_chat_usage_accumulation(usage_acc)

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
