"""
智能体工具调用循环（无知识库绑定时可选）。

当 ``AgentService._rag_chat`` 无 ``kb_ids`` 且 ``config.enable_tool_calling`` 为真时启用：
LiteLLM function calling + 平台内置工具（``integrations.langchain.tools``）+ 人工确认策略。

与 RAG 路径互斥：有 KB 时优先走检索增强，不进入本模块。
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext
from app.integrations.langchain.tools import get_all_platform_tools
from app.integrations.litellm.adapter import litellm_chat_completion
from app.models.agent import Agent
from app.tenant.agents.schemas.agent import ChatRequest, ChatResponse, PendingToolCall
from app.tenant.tools.confirmation import ToolConfirmationRequired, resolve_tool_meta
from app.tenant.tools.invoke import invoke_tool_with_context


def _tools_to_openai_schema(tools: list) -> list[dict]:
    schemas: list[dict] = []
    for t in tools:
        schema = {"type": "function", "function": {"name": t.name, "description": t.description or t.name}}
        if t.args_schema:
            schema["function"]["parameters"] = t.args_schema.model_json_schema()
        else:
            schema["function"]["parameters"] = {"type": "object", "properties": {}}
        schemas.append(schema)
    return schemas


async def _litellm_with_tools(
    model,
    messages: list[dict],
    tools: list[dict],
    *,
    temperature: float,
) -> Any:
    import litellm
    from app.integrations.litellm.adapter import resolve_litellm_model, _resolve_api_base, _ensure_chat_model_type

    _ensure_chat_model_type(model)
    kwargs: dict[str, Any] = {
        "model": resolve_litellm_model(model),
        "messages": messages,
        "temperature": temperature,
        "tools": tools,
        "tool_choice": "auto",
    }
    if model.api_key_encrypted:
        kwargs["api_key"] = model.api_key_encrypted
    api_base = _resolve_api_base(model)
    if api_base:
        kwargs["api_base"] = api_base
    return await litellm.acompletion(**kwargs)


async def run_tool_calling_chat(
    db: AsyncSession,
    ctx: TenantContext,
    agent: Agent,
    body: ChatRequest,
    *,
    agent_id: UUID,
    system_prompt: str,
) -> ChatResponse:
    """当 agent.config.enable_tool_calling 为真时，走工具调用循环。"""
    if not agent.model_config:
        raise ValueError("工具调用需要配置大模型")

    all_tools = await get_all_platform_tools(db, ctx)
    allowed = agent.config.get("tool_slugs") if isinstance(agent.config, dict) else None
    if allowed:
        allowed_set = {str(s) for s in allowed}
        tools = [t for t in all_tools if t.name in allowed_set]
    else:
        tools = all_tools

    if not tools:
        return ChatResponse(
            answer="已启用工具调用，但未找到可用工具。请绑定技能包或在 config.tool_slugs 中配置。",
            steps=[{"type": "tool_agent", "error": "no_tools"}],
        )

    # 用户确认后继续执行挂起的工具
    if body.tool_confirmed and body.pending_tool_slug:
        try:
            output = await invoke_tool_with_context(
                db,
                ctx,
                body.pending_tool_slug,
                body.pending_tool_params or {},
                confirmed=True,
                agent_id=agent_id,
                actor_user_id=ctx.user_id,
                invoke_source="agent",
            )
            return ChatResponse(
                answer=f"工具 `{body.pending_tool_slug}` 已执行。\n\n```json\n{json.dumps(output, ensure_ascii=False, indent=2)}\n```",
                steps=[
                    {
                        "type": "tool_execute",
                        "slug": body.pending_tool_slug,
                        "status": "success",
                    }
                ],
            )
        except Exception as exc:
            return ChatResponse(
                answer=f"工具执行失败：{exc}",
                steps=[{"type": "tool_execute", "slug": body.pending_tool_slug, "status": "error"}],
            )

    openai_tools = _tools_to_openai_schema(tools)
    temperature = float((agent.config or {}).get("temperature", 0.7))
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": body.query},
    ]
    max_iter = int((agent.config or {}).get("max_tool_iterations", 5))
    steps: list[dict] = [{"type": "tool_agent", "engine": "litellm_tools"}]

    for _ in range(max_iter):
        response = await _litellm_with_tools(
            agent.model_config, messages, openai_tools, temperature=temperature
        )
        choice = response.choices[0]
        message = choice.message
        tool_calls = getattr(message, "tool_calls", None) or []

        if not tool_calls:
            content = getattr(message, "content", None) or ""
            return ChatResponse(answer=str(content), steps=steps)

        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        for tc in tool_calls:
            slug = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            meta = await resolve_tool_meta(db, ctx, slug)
            if meta["require_confirmation"]:
                try:
                    await invoke_tool_with_context(
                        db,
                        ctx,
                        slug,
                        args,
                        confirmed=False,
                        agent_id=agent_id,
                        actor_user_id=ctx.user_id,
                        invoke_source="agent",
                    )
                except ToolConfirmationRequired as exc:
                    pending = PendingToolCall(
                        slug=exc.slug,
                        name=exc.tool_name,
                        description=exc.tool_description,
                        params=exc.params,
                    )
                    return ChatResponse(
                        answer=(
                            f"智能体请求调用工具「{exc.tool_name}」，需要您确认后才会执行。\n\n"
                            f"参数：```json\n{json.dumps(exc.params, ensure_ascii=False, indent=2)}\n```\n\n"
                            "请在对话中点击「确认执行」继续。"
                        ),
                        steps=steps + [{"type": "tool_confirmation_required", "slug": slug}],
                        pending_tool=pending,
                    )

            output = await invoke_tool_with_context(
                db,
                ctx,
                slug,
                args,
                confirmed=True,
                agent_id=agent_id,
                actor_user_id=ctx.user_id,
                invoke_source="agent",
            )
            steps.append({"type": "tool_call", "slug": slug, "status": "success"})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(output, ensure_ascii=False),
                }
            )

    return ChatResponse(
        answer="工具调用达到最大轮次，请简化问题后重试。",
        steps=steps + [{"type": "tool_agent", "error": "max_iterations"}],
    )
