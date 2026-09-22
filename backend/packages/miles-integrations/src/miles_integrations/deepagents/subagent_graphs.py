"""
子智能体 → DeepAgents ``CompiledSubAgent`` 适配。

每个 ``AgentSubAgentBinding``：
- 编译为单节点 LangGraph：``HumanMessage`` → ``chat_as_child_simple`` → ``AIMessage``
- ``_slug_for_binding``：``role_hint`` + child_id 前缀，作为 ``task(subagent_type=...)`` 名
- ``role_hint`` 可选：retrieval / ocr / summary / compliance / custom（见 ``_ROLE_LABELS``）

``_build_general_purpose_guard``：禁用库内置 general-purpose，强制走租户子智能体列表。
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, MessagesState, StateGraph

from miles_core.models.agent import AgentSubAgentBinding
from miles_core.models.agent.constants import SUB_AGENT_ROLE_HINTS, SUB_AGENT_ROLE_LABELS
from miles_integrations.deepagents.io import AgentServiceLike

try:
    from deepagents.middleware.subagents import CompiledSubAgent
except ImportError:
    CompiledSubAgent = None  # type: ignore[misc, assignment]

_ROLE_LABELS = SUB_AGENT_ROLE_LABELS


def _slug_for_binding(binding: AgentSubAgentBinding) -> str:
    """生成 DeepAgents task 工具可识别的子智能体 slug。"""
    if binding.role_hint and binding.role_hint in SUB_AGENT_ROLE_HINTS:
        base = binding.role_hint
    else:
        base = "agent"
    suffix = str(binding.child_agent_id).replace("-", "")[:8]
    return re.sub(r"[^a-z0-9_]", "_", f"{base}_{suffix}".lower())[:48]


def _description(binding: AgentSubAgentBinding) -> str:
    """子智能体说明（写入 CompiledSubAgent.description）。"""
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


def _make_child_node(svc: AgentServiceLike, child_id: UUID):
    """单节点图：HumanMessage → chat_as_child_simple → AIMessage。"""

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
        resp = await svc.chat_as_child_simple(
            child_id,
            query=query or "请根据上下文完成任务",
        )
        return {"messages": [AIMessage(content=resp.answer)]}

    return _run


def _build_general_purpose_guard(
    bindings: list[AgentSubAgentBinding],
) -> dict[str, Any] | None:
    """覆盖 DeepAgents 默认 general-purpose，避免委派到与主智能体等权的内置子智能体。"""
    if CompiledSubAgent is None:
        return None

    slugs = [_slug_for_binding(b) for b in bindings if b.child_agent]
    if not slugs:
        return None
    catalog = "、".join(slugs)

    async def _reject(state: MessagesState) -> dict[str, Any]:
        return {"messages": [AIMessage(content=(f"general-purpose 工位已禁用。请通过 task 工具委派到下列子智能体：{catalog}"))]}

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
    svc: AgentServiceLike,
    bindings: list[AgentSubAgentBinding],
) -> list[dict[str, Any]]:
    """DeepAgents CompiledSubAgent 列表。"""
    if CompiledSubAgent is None:
        raise ImportError("deepagents 包未安装")

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
