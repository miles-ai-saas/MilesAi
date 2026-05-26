"""
智能体工具调用循环（无知识库绑定时可选）。

当 ``AgentService._rag_chat`` 无 ``kb_ids`` 且 ``config.enable_tool_calling`` 为真时启用：
LiteLLM function calling + 平台内置工具（``integrations.langchain.tools``）+ 人工确认策略。

有 KB 时：若 ``enable_generative_tools`` 和/或绑定技能包且 ``enable_tool_calling``，
走本模块（``knowledge_search`` + 可选 generate_*）；否则走 LangGraph/线性 RAG。
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext
from app.integrations.chat.multimodal import build_user_message, resolve_media_refs
from app.integrations.langchain.tools import get_all_platform_tools, get_skill_bound_tools
from app.integrations.litellm.adapter import litellm_chat_completion
from app.models.agent import Agent
from app.tenant.agents.schemas.agent import (
    ChatArtifact,
    ChatRequest,
    ChatResponse,
    PendingToolCall,
)
from app.tenant.tools.confirmation import ToolConfirmationRequired, resolve_tool_meta
from app.tenant.tools.invoke import invoke_tool_with_context


def _artifacts_from_tool_output(output: dict) -> list[ChatArtifact]:
    """将 invoke 返回的 generate_* 字典转为 ChatArtifact（供前端预览）。"""
    if not isinstance(output, dict):
        return []
    kind = output.get("kind") or "image"
    if kind == "image":
        ids = output.get("attachment_ids") or []
        if not ids and output.get("attachment_id"):
            ids = [output["attachment_id"]]
        mime = output.get("mime_type")
        return [
            ChatArtifact(
                attachment_id=UUID(str(aid)),
                kind="image",
                mime_type=mime,
                caption=output.get("message"),
            )
            for aid in ids
        ]
    if kind == "video" and output.get("attachment_id"):
        return [
            ChatArtifact(
                attachment_id=UUID(str(output["attachment_id"])),
                kind="video",
                mime_type=output.get("mime_type") or "video/mp4",
                caption=output.get("message"),
            )
        ]
    return []


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

    from app.tenant.models.services.model_resolve import resolve_model_for_invoke

    model = await resolve_model_for_invoke(db, agent.model_config, ctx.tenant_id)

    all_tools = await get_all_platform_tools(db, ctx, agent_config=agent.config or {})
    allowed = agent.config.get("tool_slugs") if isinstance(agent.config, dict) else None
    if allowed:
        allowed_set = {str(s) for s in allowed}
        tools = [t for t in all_tools if t.name in allowed_set]
        if (agent.config or {}).get("skill_package_id"):
            for st in get_skill_bound_tools():
                if st.name not in {t.name for t in tools}:
                    tools.append(st)
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
    max_media = int((agent.config or {}).get("max_media_per_turn", 4))
    media_parts = (
        await resolve_media_refs(db, ctx, body.media, max_count=max_media) if body.media else []
    )
    chat_query = body.query.strip() or ("请根据附图回答。" if media_parts else body.query)
    user_msg = build_user_message(query=chat_query, media_parts=media_parts)
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        user_msg,
    ]
    max_iter = int((agent.config or {}).get("max_tool_iterations", 5))
    steps: list[dict] = [{"type": "tool_agent", "engine": "litellm_tools"}]
    artifacts: list[ChatArtifact] = []

    for _ in range(max_iter):
        response = await _litellm_with_tools(
            model, messages, openai_tools, temperature=temperature
        )
        choice = response.choices[0]
        message = choice.message
        tool_calls = getattr(message, "tool_calls", None) or []

        if not tool_calls:
            content = getattr(message, "content", None) or ""
            return ChatResponse(answer=str(content), steps=steps, artifacts=artifacts)

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
            pending_job_id = (
                output.get("generative_job_id")
                if isinstance(output, dict) and output.get("status") == "pending"
                else None
            )
            if pending_job_id:
                steps.append(
                    {
                        "type": "generative_job",
                        "slug": slug,
                        "job_id": pending_job_id,
                        "kind": output.get("kind") or "video",
                        "status": "pending",
                    }
                )
                job_kind = str(output.get("kind") or "video")
                default_msg = (
                    "图片生成任务已提交，完成后将自动展示预览。"
                    if job_kind == "image"
                    else "视频生成任务已提交，完成后将自动展示预览。"
                )
                return ChatResponse(
                    answer=str(output.get("message") or default_msg),
                    steps=steps,
                    generative_jobs=[
                        {
                            "id": pending_job_id,
                            "kind": job_kind,
                            "status": "pending",
                        }
                    ],
                )
            artifacts.extend(_artifacts_from_tool_output(output))
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
        artifacts=artifacts,
    )
