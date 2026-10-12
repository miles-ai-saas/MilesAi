"""
DeepAgents 原生规划与 ``task`` 工具委派。

组件
----
- ``create_deep_agent`` + 主模型 ``PlatformChatModel``（LangChain）
- ``build_compiled_subagents``：每个 binding 一个 CompiledSubAgent runnable
- ``checkpointer``：与 RAG 图共用 ``integrations.langgraph.checkpointer``（``thread_id`` 前缀 ``deep:``）

子工位内仅调用 ``AgentService.chat_as_child_simple``（内部委托 ``AgentService.chat_as_child``；可含 KB RAG / 子流程，不再嵌套子 Agent 规划）。
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from miles_core.models.agent import Agent, AgentSubAgentBinding
from miles_core.models.agent.constants import AgentPlanner
from miles_integrations.deepagents.io import AgentServiceLike, ParentChatInput, SubAgentPlanResult
from miles_integrations.deepagents.subagent_graphs import _slug_for_binding, build_compiled_subagents
from miles_integrations.langchain.chat_models import OnDelta, get_chat_model
from miles_integrations.langgraph.checkpointer import get_checkpointer

try:
    from deepagents import create_deep_agent
except ImportError:
    create_deep_agent = None  # type: ignore[misc, assignment]


def deepagents_importable() -> bool:
    """运行时检测 deepagents 包是否已安装。"""
    return create_deep_agent is not None


def _thread_id(parent: Agent, body: ParentChatInput) -> str:
    """DeepAgents checkpointer 线程 id。"""
    suffix = (body.conversation_id or "default").strip()[:128] or "default"
    return f"deep:{parent.tenant_id}:{parent.id}:{suffix}"


def _chunk_text(content: Any) -> str:
    """把 AIMessageChunk.content（str 或 part 列表）压成纯文本。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
            else:
                text = getattr(item, "text", None)
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return str(content)


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


async def _run_deepagents_astream(
    agent: Any,
    *,
    query: str,
    config: dict[str, Any],
    on_delta: OnDelta,
) -> list[Any]:
    """``astream(messages+values)``：主模型 content 片断经 ``on_delta``；跳过 tool_call 片。"""
    messages: list[Any] = []
    async for item in agent.astream(
        {"messages": [HumanMessage(content=query)]},
        config=config,
        stream_mode=["messages", "values"],
    ):
        # LangGraph：list stream_mode → (mode, payload)
        if not isinstance(item, tuple) or len(item) != 2:
            continue
        mode, payload = item
        if mode == "messages":
            msg = payload[0] if isinstance(payload, tuple) else payload
            if not isinstance(msg, AIMessageChunk):
                continue
            if getattr(msg, "tool_call_chunks", None):
                continue
            text = _chunk_text(msg.content)
            if text:
                await on_delta(text)
        elif mode == "values" and isinstance(payload, dict):
            messages = list(payload.get("messages") or messages)
    return messages


async def run_deepagents_chat(
    svc: AgentServiceLike,
    parent: Agent,
    bindings: list[AgentSubAgentBinding],
    body: ParentChatInput,
    *,
    on_delta: OnDelta | None = None,
) -> SubAgentPlanResult:
    """
    DeepAgents 主循环：主模型通过 ``task`` 工具委派 ``CompiledSubAgent``。

    ``body`` 为 L1 ``chat_entry`` 从 ``ChatRequest`` 解包的中性输入；
    返回 ``SubAgentPlanResult``，由 L1 包回 ``ChatResponse``。

    ``on_delta`` 非空时走 ``astream``，把主模型 content token 推给调用方
    （tool_call 片断跳过；子工位内部仍整段）。

    ``recursion_limit`` 来自 ``config.max_plan_iterations``（默认 12）。
    """
    if create_deep_agent is None:
        raise ImportError("deepagents 包未安装")

    if not parent.model_config:
        raise ValueError("DeepAgents 需要主智能体配置大模型")

    subagents = build_compiled_subagents(
        svc,
        bindings,
        conversation_id=body.conversation_id,
        inputs=body.inputs,
    )
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
    # 长期 → 近期，与平台规划 / RAG 一致。
    if body.long_term_block:
        system_prompt = f"{system_prompt}{body.long_term_block}"
    if body.history_block:
        system_prompt = f"{system_prompt}{body.history_block}"

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
    config: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": max(max_iter, 4),
    }

    if on_delta is not None:
        messages = await _run_deepagents_astream(
            agent, query=body.query, config=config, on_delta=on_delta
        )
    else:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=body.query)]},
            config=config,
        )
        messages = result.get("messages") or []

    answer = _extract_answer(messages)
    if not answer:
        answer = "DeepAgents 未产生有效回答，请检查子智能体配置与模型。"

    steps = _extract_steps(messages, bindings)
    if body.long_term_item_count or body.long_term_block:
        steps.append(
            {
                "type": "user_memory",
                "items": body.long_term_item_count,
                "chars": len(body.long_term_block or ""),
                "route": "subagent",
            }
        )
    if body.history_message_count:
        steps.append(
            {
                "type": "chat_memory",
                "history_messages": body.history_message_count,
                "route": "subagent",
                "engine": AgentPlanner.DEEPAGENTS.value,
            }
        )
    return SubAgentPlanResult(answer=answer, steps=steps)
