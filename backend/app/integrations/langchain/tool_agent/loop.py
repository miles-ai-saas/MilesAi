"""LiteLLM 多轮 function calling 主循环。"""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError
from app.core.tenant import TenantContext
from app.integrations.chat.multimodal import build_user_message, messages_contain_image, resolve_media_refs
from app.integrations.langchain.tool_agent.artifacts import artifacts_from_tool_output
from app.integrations.langchain.tool_agent.litellm_tools import (
    _litellm_with_tools,
    _tools_to_openai_schema,
)
from app.integrations.langchain.tool_agent.parse import (
    _GENERATIVE_INTENT_PHRASES,
    _extract_tool_params_from_text,
    _looks_like_tool_call_simulation,
)
from app.integrations.langchain.tools import get_all_platform_tools, get_skill_bound_tools
from app.models.agent import Agent
from app.tenant.agents.schemas.agent import (
    ChatArtifact,
    ChatRequest,
    ChatResponse,
    PendingToolCall,
)
from app.tenant.models.services.model_resolve import resolve_model_for_invoke
from app.tenant.models.services.usage import UsageRecordContext, record_litellm_response_usage
from app.tenant.tools.confirmation import ToolConfirmationRequired, resolve_tool_meta
from app.tenant.tools.invoke import invoke_tool_with_context


async def run_tool_calling_chat(
    db: AsyncSession,
    ctx: TenantContext,
    agent: Agent,
    body: ChatRequest,
    *,
    agent_id: UUID,
    system_prompt: str,
) -> ChatResponse:
    """
    LiteLLM 多轮 function calling 主循环。

    流程：解析模型 → 按 ``tool_slugs`` 过滤工具 → 多轮 ``acompletion`` →
    ``invoke_tool_with_context`` 执行；需确认时返回 ``pending_tool``；
    ``generate_*`` 异步任务返回 ``generative_jobs``；同步附件写入 ``artifacts``。
    """
    if not agent.model_config:
        raise ValueError("工具调用需要配置大模型")

    model = await resolve_model_for_invoke(db, agent.model_config, ctx.tenant_id)
    usage_ctx = UsageRecordContext(
        db=db,
        tenant_id=ctx.tenant_id,
        model=model,
        source="chat",
        source_id=agent_id,
    )

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
            confirm_params = dict(body.pending_tool_params or {})
            if body.pending_tool_slug == "generate_image":
                from app.integrations.generative.request_prefs import resolve_image_n

                confirm_params["n"] = resolve_image_n(confirm_params.get("n"))
            output = await invoke_tool_with_context(
                db,
                ctx,
                body.pending_tool_slug,
                confirm_params,
                confirmed=True,
                agent_id=agent_id,
                actor_user_id=ctx.user_id,
                invoke_source="agent",
            )
            confirm_artifacts = artifacts_from_tool_output(output) if isinstance(output, dict) else []
            confirm_message = str(output.get("message") if isinstance(output, dict) else output)
            confirm_jobs: list[dict] = []
            if isinstance(output, dict) and output.get("status") == "pending":
                confirm_jobs.append(
                    {
                        "id": output.get("generative_job_id", ""),
                        "kind": output.get("kind", "image"),
                        "status": "pending",
                    }
                )
            return ChatResponse(
                answer=confirm_message or f"工具 `{body.pending_tool_slug}` 已执行。",
                steps=[
                    {
                        "type": "tool_execute",
                        "slug": body.pending_tool_slug,
                        "status": "success",
                    }
                ],
                artifacts=confirm_artifacts,
                generative_jobs=confirm_jobs,
            )
        except Exception as exc:
            return ChatResponse(
                answer=f"工具执行失败：{exc}",
                steps=[{"type": "tool_execute", "slug": body.pending_tool_slug, "status": "error", "error": str(exc)}],
            )

    openai_tools = _tools_to_openai_schema(tools)
    temperature = float((agent.config or {}).get("temperature", 0.7))
    max_media = int((agent.config or {}).get("max_media_per_turn", 10))
    body_media_count = len(body.media) if body.media else 0
    media_parts = await resolve_media_refs(db, ctx, body.media, max_count=max_media) if body.media else []
    chat_query = body.query.strip() or ("请根据附图回答。" if media_parts else body.query)
    user_msg = build_user_message(query=chat_query, media_parts=media_parts)
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        user_msg,
    ]
    max_iter = int((agent.config or {}).get("max_tool_iterations", 5))
    steps: list[dict] = [
        {"type": "tool_agent", "engine": "litellm_tools", "media_count": body_media_count, "media_resolved": len(media_parts), "model_type": model.model_type}
    ]
    artifacts: list[ChatArtifact] = []
    _tool_sim_retried = False
    _tool_names = [t.name for t in tools]
    _tools_by_name = {t.name: t for t in tools}

    if body_media_count > 0 and model.model_type != "vision" and messages_contain_image(messages):
        steps.append(
            {"type": "multimodal_warning", "message": f"当前模型类型为 {model.model_type}（非 vision），图片可能无法被模型识别", "model_type": model.model_type}
        )

    for _ in range(max_iter):
        response = await _litellm_with_tools(model, messages, openai_tools, temperature=temperature)
        await record_litellm_response_usage(usage_ctx, response)
        choice = response.choices[0]
        message = choice.message
        tool_calls = getattr(message, "tool_calls", None) or []

        if not tool_calls:
            content = getattr(message, "content", None) or ""
            if not _tool_sim_retried and _looks_like_tool_call_simulation(content, _tool_names):
                _tool_sim_retried = True
                # 优先尝试从文本中提取工具参数并直接执行（自救助）
                extracted = _extract_tool_params_from_text(content, _tools_by_name)
                if extracted:
                    slug, params = extracted
                    try:
                        meta = await resolve_tool_meta(db, ctx, slug)
                    except Exception:
                        meta = None
                    if meta and not meta.get("require_confirmation"):
                        # 无需确认：直接执行并返回结果
                        try:
                            output = await invoke_tool_with_context(
                                db,
                                ctx,
                                slug,
                                params,
                                confirmed=True,
                                agent_id=agent_id,
                                actor_user_id=ctx.user_id,
                                invoke_source="agent",
                            )
                        except Exception as exc:
                            steps.append({"type": "tool_simulation_corrected", "message": f"提取 JSON 参数后执行 {slug} 失败: {exc}，追加纠正提示"})
                            messages.append({"role": "assistant", "content": content})
                            messages.append(
                                {
                                    "role": "user",
                                    "content": (
                                        "你刚才输出的 JSON 无法被系统正确解析执行。"
                                        "请直接通过 function calling 机制（tool_use）调用工具，"
                                        "而不是在文字中输出 JSON 参数。"
                                        "如需生图，请发起真正的 tool_call。"
                                    ),
                                }
                            )
                            continue
                        exec_artifacts = artifacts_from_tool_output(output) if isinstance(output, dict) else []
                        exec_jobs: list[dict] = []
                        exec_message = str(output.get("message") if isinstance(output, dict) else output) or f"已执行工具 {slug}"
                        if isinstance(output, dict) and output.get("status") == "pending":
                            exec_jobs.append(
                                {
                                    "id": output.get("generative_job_id", ""),
                                    "kind": output.get("kind", "image"),
                                    "status": "pending",
                                }
                            )
                        steps.append({"type": "tool_simulation_extracted", "slug": slug, "message": "从 LLM 文本输出中提取 JSON 参数并直接执行了工具"})
                        return ChatResponse(
                            answer=exec_message,
                            steps=steps,
                            artifacts=exec_artifacts,
                            generative_jobs=exec_jobs,
                        )
                # 提取失败：判断是否为"意图短语无 JSON"兜底
                is_intent_only = any(phrase in content for phrase in _GENERATIVE_INTENT_PHRASES)
                if is_intent_only and any("image" in name and "video" not in name for name in _tool_names):
                    # LLM 表达了生图意图但没有 JSON → 用用户原始 query 作为 prompt 直接生图
                    image_tool = next((name for name in _tool_names if "image" in name and "video" not in name), _tool_names[0])
                    fallback_query = body.query.strip()
                    if not fallback_query:
                        steps.append({"type": "tool_simulation_no_query", "message": "LLM 表达了生成意图但无法提取参数，且用户 query 为空"})
                        return ChatResponse(answer="请描述您想要生成的图片内容。", steps=steps)
                    try:
                        meta = await resolve_tool_meta(db, ctx, image_tool)
                    except Exception:
                        meta = None
                    if meta and not meta.get("require_confirmation"):
                        try:
                            output = await invoke_tool_with_context(
                                db,
                                ctx,
                                image_tool,
                                {"prompt": fallback_query},
                                confirmed=True,
                                agent_id=agent_id,
                                actor_user_id=ctx.user_id,
                                invoke_source="agent",
                            )
                        except Exception as exc:
                            steps.append({"type": "tool_simulation_corrected", "message": f"用原始 query 兜底执行 {image_tool} 失败: {exc}"})
                            messages.append({"role": "assistant", "content": content})
                            messages.append(
                                {
                                    "role": "user",
                                    "content": "请直接通过 function calling 调用 generate_image 工具。",
                                }
                            )
                            continue
                        exec_artifacts = artifacts_from_tool_output(output) if isinstance(output, dict) else []
                        exec_jobs: list[dict] = []
                        exec_message = str(output.get("message") if isinstance(output, dict) else output) or "已开始生成图片"
                        if isinstance(output, dict) and output.get("status") == "pending":
                            exec_jobs.append(
                                {
                                    "id": output.get("generative_job_id", ""),
                                    "kind": output.get("kind", "image"),
                                    "status": "pending",
                                }
                            )
                        steps.append(
                            {
                                "type": "tool_simulation_intent_fallback",
                                "slug": image_tool,
                                "message": "LLM 表达了生成意图但无 JSON，用原始 query 作为 prompt 兜底执行",
                                "fallback_query_preview": fallback_query[:200],
                            }
                        )
                        return ChatResponse(
                            answer=exec_message,
                            steps=steps,
                            artifacts=exec_artifacts,
                            generative_jobs=exec_jobs,
                        )
                # 其他提取失败：回退到纠正提示重试
                steps.append({"type": "tool_simulation_corrected", "message": "LLM 在文字中模拟了工具调用，已追加纠正提示"})
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "你刚才在文字中描述了工具调用，但并未真正发起 function call。"
                            "请直接通过 tool_use 机制调用工具，不要用文字描述调用过程。"
                            "如需生图，立即调用 generate_image 工具并传入参数。"
                        ),
                    }
                )
                continue
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

        # 防重复：同一轮对话中 generate_image / generate_video 只执行首次调用，
        # 避免 LLM 因多张参考图而发起多次 tool_call 导致生成数量翻倍。
        _generative_deduplicated: list = []
        _seen_generative: set[str] = set()
        for tc in tool_calls:
            slug = tc.function.name
            if slug in ("generate_image", "generate_video"):
                if slug in _seen_generative:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": f"工具 {slug} 已执行，本次重复调用自动合并。",
                        }
                    )
                    continue
                _seen_generative.add(slug)
            _generative_deduplicated.append(tc)

        for tc in _generative_deduplicated:
            slug = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            try:
                meta = await resolve_tool_meta(db, ctx, slug)
            except BadRequestError as exc:
                steps.append({"type": "tool_call", "slug": slug, "status": "error", "error": str(exc)})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": f"工具不存在: {slug}",
                    }
                )
                return ChatResponse(
                    answer=f"智能体尝试调用工具「{slug}」，但该工具未找到。\n\n可能原因：\n1. 工具 slug 配置有误\n2. 自定义工具已被删除或禁用\n3. 内置工具 slug 拼写错误\n\n请在智能体「能力」步骤中检查 tool_slugs 配置，并确认工具仍在「平台工具」中。",
                    steps=steps,
                    artifacts=artifacts,
                )
            except Exception:
                steps.append({"type": "tool_call", "slug": slug, "status": "error", "error": "resolve_tool_meta 失败"})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": f"工具解析失败: {slug}",
                    }
                )
                raise
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
                    # 生图工具的确认描述已在 policy 中生成，直接展示
                    description_text = ""
                    if exc.tool_description and slug == "generate_image":
                        description_text = f"\n\n{exc.tool_description}"
                    return ChatResponse(
                        answer=(
                            f"智能体请求调用工具「{exc.tool_name}」，需要您确认后才会执行。"
                            f"{description_text}\n\n"
                            f"参数：```json\n{json.dumps(exc.params, ensure_ascii=False, indent=2)}\n```\n\n"
                            "请在对话中点击「确认执行」继续。"
                        ),
                        steps=steps + [{"type": "tool_confirmation_required", "slug": slug}],
                        pending_tool=pending,
                    )

            try:
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
            except ToolConfirmationRequired:
                raise
            except BadRequestError as exc:
                steps.append({"type": "tool_call", "slug": slug, "status": "error", "error": str(exc)})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(exc),
                    }
                )
                if slug in ("generate_image", "generate_video"):
                    artifacts.append(
                        ChatArtifact(
                            kind="image" if slug == "generate_image" else "video",
                            status="failed",
                            error_message=str(exc),
                            caption=str(exc),
                        )
                    )
                return ChatResponse(
                    answer=f"工具「{slug}」执行失败：{exc}",
                    steps=steps,
                    artifacts=artifacts,
                )
            pending_job_id = output.get("generative_job_id") if isinstance(output, dict) and output.get("status") == "pending" else None
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
                default_msg = "图片生成任务已提交，完成后将自动展示预览。" if job_kind == "image" else "视频生成任务已提交，完成后将自动展示预览。"
                pending_out = dict(output) if isinstance(output, dict) else {}
                pending_out.setdefault("status", "pending")
                pending_out.setdefault("kind", job_kind)
                pending_out.setdefault("generative_job_id", pending_job_id)
                artifacts.extend(artifacts_from_tool_output(pending_out))
                return ChatResponse(
                    answer=str(output.get("message") or default_msg),
                    steps=steps,
                    artifacts=artifacts,
                    generative_jobs=[
                        {
                            "id": pending_job_id,
                            "kind": job_kind,
                            "status": "pending",
                        }
                    ],
                )
            artifacts.extend(artifacts_from_tool_output(output))
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
