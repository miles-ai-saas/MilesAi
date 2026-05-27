"""
DeepAgents 原生规划与 ``task`` 工具委派。

组件
----
- ``create_deep_agent`` + 主模型 ``PlatformChatModel``（LangChain）
- ``build_compiled_subagents``：每个 binding 一个 CompiledSubAgent runnable
- ``checkpointer``：与 RAG 图共用 ``integrations.langgraph.checkpointer``（``thread_id`` 前缀 ``deep:``）

子工位内仅调用 ``AgentService.chat_as_child``（可含 KB RAG / 子流程，不再嵌套子 Agent 规划）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.integrations.deepagents.subagent_graphs import _slug_for_binding, build_compiled_subagents
from app.integrations.langchain.chat_models import get_chat_model
from app.integrations.langgraph.checkpointer import get_checkpointer
from app.tenant.agents.constants import AgentPlanner
from app.tenant.agents.schemas.agent import ChatRequest, ChatResponse
from app.models.agent import Agent, AgentSubAgentBinding

try:
    from deepagents import create_deep_agent
except ImportError:
    create_deep_agent = None  # type: ignore[misc, assignment]

if TYPE_CHECKING:
    from app.tenant.agents.services.agent import AgentService


def deepagents_importable() -> bool:
    """运行时检测 deepagents 包是否已安装。"""
    return create_deep_agent is not None


def _thread_id(parent: Agent, body: ChatRequest) -> str:
    """DeepAgents checkpointer 线程 id。"""
    suffix = (body.conversation_id or "default").strip()[:128] or "default"
    return f"deep:{parent.tenant_id}:{parent.id}:{suffix}"


def _extract_answer(messages: list[Any]) -> str:
    """从消息列表取最后一条 AIMessage 正文。"""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return str(msg.content)
    return ""


def _extract_steps(messages: list[Any], bindings: list[AgentSubAgentBinding]) -> list[dict]:
    """从 tool_calls / ToolMessage 提取可展示的委派步骤。"""
    slug_to_binding = {}
    for b in bindings:
        slug_to_binding[_slug_for_binding(b)] = b

    steps: list[dict] = [
        {
            "type": "planner",
            "engine": AgentPlanner.DEEPAGENTS.value,
            "mode": "task_delegation",
        }
    ]
    for msg in messages:
        if isinstance(msg, ToolMessage):
            name = getattr(msg, "name", None) or ""
            if name == "task" or "task" in str(name).lower():
                content = str(msg.content or "")[:500]
                steps.append(
                    {
                        "type": "subagent",
                        "tool": "task",
                        "output_preview": content,
                    }
                )
        tool_calls = getattr(msg, "tool_calls", None) or []
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            if tc.get("name") != "task":
                continue
            args = tc.get("args") or {}
            sub_name = args.get("subagent_type") or args.get("name") or args.get("subagent")
            task = args.get("description") or args.get("task") or ""
            binding = slug_to_binding.get(str(sub_name)) if sub_name else None
            steps.append(
                {
                    "type": "subagent_dispatch",
                    "sub_agent_name": binding.child_agent.name if binding and binding.child_agent else sub_name,
                    "sub_agent_id": str(binding.child_agent_id) if binding else None,
                    "role_hint": binding.role_hint if binding else None,
                    "task": str(task)[:300],
                }
            )
    return steps


async def run_deepagents_chat(
    svc: AgentService,
    parent: Agent,
    bindings: list[AgentSubAgentBinding],
    body: ChatRequest,
) -> ChatResponse:
    """
    DeepAgents 主循环：主模型通过 ``task`` 工具委派 ``CompiledSubAgent``。

    ``recursion_limit`` 来自 ``config.max_plan_iterations``（默认 12）。
    """
    if create_deep_agent is None:
        raise ImportError("deepagents 包未安装")

    if not parent.model_config:
        raise ValueError("DeepAgents 需要主智能体配置大模型")

    subagents = build_compiled_subagents(svc, bindings)
    if not subagents:
        raise ValueError("无可用子智能体绑定")

    catalog_lines = []
    for s in subagents:
        catalog_lines.append(f"- {s['name']}: {s['description']}")
    catalog = "\n".join(catalog_lines)

    parent_prompt = await svc.resolve_system_prompt(parent)
    system_prompt = (
        f"{parent_prompt}\n\n"
        "你是主协调智能体。将用户问题拆解后，通过 task 工具委派给下列子智能体工位，"
        "不要编造子智能体未返回的内容。\n"
        f"可用子智能体（task 的 subagent_type 使用 name 字段）：\n{catalog}"
    )

    llm = get_chat_model(
        parent.model_config,
        temperature=float((parent.config or {}).get("temperature", 0.7)),
    )
    checkpointer = get_checkpointer()
    agent = create_deep_agent(
        model=llm,
        system_prompt=system_prompt,
        subagents=subagents,
        checkpointer=checkpointer,
    )

    max_iter = int((parent.config or {}).get("max_plan_iterations", 12))
    thread_id = _thread_id(parent, body)
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=body.query)]},
        config={
            "configurable": {"thread_id": thread_id},
            "recursion_limit": max(max_iter, 4),
        },
    )

    messages = result.get("messages") or []
    answer = _extract_answer(messages)
    if not answer:
        answer = "DeepAgents 未产生有效回答，请检查子智能体配置与模型。"

    steps = _extract_steps(messages, bindings)
    return ChatResponse(answer=answer, sources=[], steps=steps)
