"""将租户子智能体编译为 DeepAgents CompiledSubAgent（runnable 内调用 chat_as_child）。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, MessagesState, StateGraph

from app.tenant.agents.schemas.agent import ChatRequest
from app.models.agent import AgentSubAgentBinding

if TYPE_CHECKING:
    from app.tenant.agents.services.agent import AgentService

_ROLE_LABELS = {
    "retrieval": "知识检索",
    "ocr": "OCR 识别",
    "summary": "摘要归纳",
    "compliance": "合规审查",
    "custom": "自定义",
}


def _slug_for_binding(binding: AgentSubAgentBinding) -> str:
    if binding.role_hint and binding.role_hint in _ROLE_LABELS:
        base = binding.role_hint
    else:
        base = "agent"
    suffix = str(binding.child_agent_id).replace("-", "")[:8]
    return re.sub(r"[^a-z0-9_]", "_", f"{base}_{suffix}".lower())[:48]


def _description(binding: AgentSubAgentBinding) -> str:
    child = binding.child_agent
    if not child:
        return "子智能体工位"
    role = _ROLE_LABELS.get(binding.role_hint or "", binding.role_hint or "")
    parts = [f"名称：{child.name}"]
    if role:
        parts.append(f"职责：{role}")
    if child.description:
        parts.append(f"说明：{child.description[:200]}")
    return "；".join(parts)


def _make_child_node(svc: AgentService, child_id: UUID):
    async def _run(state: MessagesState) -> dict[str, Any]:
        query = ""
        for msg in reversed(state.get("messages") or []):
            if isinstance(msg, HumanMessage):
                query = str(msg.content or "")
                break
        if not query:
            msgs = state.get("messages") or []
            if msgs:
                query = str(getattr(msgs[-1], "content", "") or "")
        resp = await svc.chat_as_child(
            child_id,
            ChatRequest(query=query or "请根据上下文完成任务"),
        )
        return {"messages": [AIMessage(content=resp.answer)]}

    return _run


def _build_general_purpose_guard(
    bindings: list[AgentSubAgentBinding],
) -> dict[str, Any] | None:
    """覆盖 DeepAgents 默认 general-purpose，避免委派到与主智能体等权的内置子智能体。"""
    from deepagents.middleware.subagents import CompiledSubAgent

    slugs = [_slug_for_binding(b) for b in bindings if b.child_agent]
    if not slugs:
        return None
    catalog = "、".join(slugs)

    async def _reject(state: MessagesState) -> dict[str, Any]:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "general-purpose 工位已禁用。请通过 task 工具委派到下列子智能体："
                        f"{catalog}"
                    )
                )
            ]
        }

    graph = StateGraph(MessagesState)
    graph.add_node("reject", _reject)
    graph.add_edge(START, "reject")
    graph.add_edge("reject", END)
    return CompiledSubAgent(
        name="general-purpose",
        description=f"已禁用，请改用：{catalog}",
        runnable=graph.compile(),
    )


def build_compiled_subagents(
    svc: AgentService,
    bindings: list[AgentSubAgentBinding],
) -> list[dict[str, Any]]:
    """DeepAgents CompiledSubAgent 列表。"""
    from deepagents.middleware.subagents import CompiledSubAgent

    out: list[CompiledSubAgent] = []
    guard = _build_general_purpose_guard(bindings)
    if guard:
        out.append(guard)
    for b in bindings:
        if not b.child_agent:
            continue
        graph = StateGraph(MessagesState)
        graph.add_node("work", _make_child_node(svc, b.child_agent_id))
        graph.add_edge(START, "work")
        graph.add_edge("work", END)
        runnable = graph.compile()
        out.append(
            CompiledSubAgent(
                name=_slug_for_binding(b),
                description=_description(b),
                runnable=runnable,
            )
        )
    return out
