"""单轮对话收尾：RAG 路由解析、出站合规与调用记录。"""

from __future__ import annotations

from uuid import UUID

from app.integrations.langgraph.runner import should_use_langgraph_rag
from app.models.agent import Agent
from app.tenant.agents.schemas.agent import ChatResponse
from app.tenant.agents.services.agent.serialization import should_use_skill_tools_with_kb
from app.tenant.agents.services.call_records import ChatCallRecorder
from app.tenant.compliance.constants import SCAN_MODULE_AGENT_CHAT
from app.tenant.compliance.services.compliance import ComplianceService
from app.tenant.hooks.models import HookScope, HookTrigger
from app.tenant.hooks.services.runner import HookRunner


class AgentChatTurnMixin:
    """单轮收尾与 RAG 路由；依赖 ``AgentCrudMixin`` 加载智能体。"""

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

    def _resolve_rag_route(self, agent: Agent, kb_ids: list[str]) -> str:
        cfg = agent.config if isinstance(agent.config, dict) else {}
        if not kb_ids:
            if (cfg.get("enable_tool_calling") or cfg.get("enable_generative_tools")) and agent.model_config_id:
                return "tool_agent"
            return "direct_llm"
        if should_use_skill_tools_with_kb(agent, kb_ids):
            return "tool_agent"
        if should_use_langgraph_rag(agent, kb_ids=kb_ids):
            return "rag"
        return "rag"

    async def _complete_chat_turn(
        self,
        recorder: ChatCallRecorder,
        route: str,
        *,
        compliance: ComplianceService,
        hooks: HookRunner,
        agent_id: UUID,
        hook_payload: dict,
        response: ChatResponse,
    ) -> ChatResponse:
        """出站合规 + Hook 收尾，并写入调用记录。"""
        recorder.set_route(route)
        try:
            finished = await self._finish_chat_turn(
                compliance=compliance,
                hooks=hooks,
                agent_id=agent_id,
                hook_payload=hook_payload,
                response=response,
            )
            await recorder.record_success(finished, route=route)
            return finished
        except Exception as exc:
            await recorder.record_failure(exc, route=route, response=response)
            raise
