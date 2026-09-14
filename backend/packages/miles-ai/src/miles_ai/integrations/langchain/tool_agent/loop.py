"""LiteLLM 多轮 function calling 主循环（工具 schema 与执行器由 L1 装配注入）。"""

from __future__ import annotations

import json
from uuid import UUID

from miles_ai.integrations.chat.multimodal import build_user_message, messages_contain_image, resolve_media_refs
from miles_ai.integrations.langchain.tool_agent.artifacts import artifacts_from_tool_output
from miles_ai.integrations.langchain.tool_agent.litellm_tools import (
    _litellm_with_tools,
    _tools_to_openai_schema,
)
from miles_ai.integrations.langchain.tool_agent.parse import (
    _GENERATIVE_INTENT_PHRASES,
    _extract_tool_params_from_text,
    _looks_like_tool_call_simulation,
)
from miles_ai.integrations.langchain.tool_agent.tool_contract import ToolConfirmationSignal, ToolExecutor
from miles_ai.integrations.langchain.tools import get_skill_bound_tools, select_agent_tools
from miles_ai.integrations.litellm.adapter import extract_litellm_usage
from miles_ai.integrations.litellm.usage_sink import UsageSink
from miles_common.exceptions import BadRequestError
from miles_core.models.agent import Agent
from miles_core.models.agent.chat_io import (
    ChatArtifact,
    ChatRequest,
    ChatResponse,
    PendingToolCall,
)
from miles_core.models.media.reader import MediaReader
from miles_core.models.model import ModelConfig

# 同轮内允许多次调用的生成类工具（其余工具按需重复调用是合法的）
_GENERATIVE_SLUGS = frozenset({"generate_image", "generate_video"})


def _pending_job_entry(job_id: object, kind: object) -> dict:
    """构造前端轮询用的 ``generative_jobs`` 条目（id / kind / status）。"""
    return {"id": job_id, "kind": kind, "status": "pending"}


async def _resume_confirmed_tool(body: ChatRequest, tool_executor: ToolExecutor) -> ChatResponse | None:
    """处理「用户点击确认后」的续接请求。

    非续接请求返回 ``None``（调用方继续走正常多轮循环）；续接请求一律返回响应：
    执行成功回结果与产出物，执行异常转为失败响应（不向外抛）。
    """
    if not (body.tool_confirmed and body.pending_tool_slug):
        return None

    slug = body.pending_tool_slug
    try:
        confirm_params = dict(body.pending_tool_params or {})
        if slug == "generate_image":
            from miles_ai.integrations.generative.request_prefs import resolve_image_n

            confirm_params["n"] = resolve_image_n(confirm_params.get("n"))
        output = await tool_executor.invoke(slug, confirm_params, confirmed=True)
        confirm_artifacts = artifacts_from_tool_output(output) if isinstance(output, dict) else []
        confirm_message = str(output.get("message") if isinstance(output, dict) else output)
        confirm_jobs = (
            [_pending_job_entry(output.get("generative_job_id", ""), output.get("kind", "image"))]
            if isinstance(output, dict) and output.get("status") == "pending"
            else []
        )
        return ChatResponse(
            answer=confirm_message or f"工具 `{slug}` 已执行。",
            steps=[{"type": "tool_execute", "slug": slug, "status": "success"}],
            artifacts=confirm_artifacts,
            generative_jobs=confirm_jobs,
        )
    except Exception as exc:
        return ChatResponse(
            answer=f"工具执行失败：{exc}",
            steps=[{"type": "tool_execute", "slug": slug, "status": "error", "error": str(exc)}],
        )


async def _recover_from_tool_simulation(
    content: str,
    *,
    tool_names: list[str],
    tools_by_name: dict,
    tool_executor: ToolExecutor,
    messages: list[dict],
    steps: list[dict],
    body: ChatRequest,
) -> ChatResponse | None:
    """LLM 在正文里「模拟」了工具调用（而非真正发起 tool_call）时的自救助。

    返回非 ``None`` 表示应终止并回复该响应；返回 ``None`` 表示已向 ``messages``
    追加纠正提示，调用方应进入下一轮重试。
    """
    extracted = _extract_tool_params_from_text(content, tools_by_name)
    if extracted:
        slug, params = extracted
        try:
            meta = await tool_executor.meta(slug)
        except Exception:
            meta = None
        if meta and not meta.get("require_confirmation"):
            try:
                output = await tool_executor.invoke(slug, params, confirmed=True)
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
                return None
            exec_artifacts = artifacts_from_tool_output(output) if isinstance(output, dict) else []
            exec_jobs: list[dict] = []
            exec_message = str(output.get("message") if isinstance(output, dict) else output) or f"已执行工具 {slug}"
            if isinstance(output, dict) and output.get("status") == "pending":
                exec_jobs.append(_pending_job_entry(output.get("generative_job_id", ""), output.get("kind", "image")))
            steps.append({"type": "tool_simulation_extracted", "slug": slug, "message": "从 LLM 文本输出中提取 JSON 参数并直接执行了工具"})
            return ChatResponse(
                answer=exec_message,
                steps=steps,
                artifacts=exec_artifacts,
                generative_jobs=exec_jobs,
            )

    # 提取失败：判断是否为「表达了生成意图但没给 JSON」的兜底场景
    is_intent_only = any(phrase in content for phrase in _GENERATIVE_INTENT_PHRASES)
    image_tool = next((name for name in tool_names if "image" in name and "video" not in name), None)
    if is_intent_only and image_tool is not None:
        # LLM 表达了生图意图但没有 JSON → 用用户原始 query 作为 prompt 直接生图
        fallback_query = body.query.strip()
        if not fallback_query:
            steps.append({"type": "tool_simulation_no_query", "message": "LLM 表达了生成意图但无法提取参数，且用户 query 为空"})
            return ChatResponse(answer="请描述您想要生成的图片内容。", steps=steps)
        try:
            meta = await tool_executor.meta(image_tool)
        except Exception:
            meta = None
        if meta and not meta.get("require_confirmation"):
            try:
                output = await tool_executor.invoke(image_tool, {"prompt": fallback_query}, confirmed=True)
            except Exception as exc:
                steps.append({"type": "tool_simulation_corrected", "message": f"用原始 query 兜底执行 {image_tool} 失败: {exc}"})
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {
                        "role": "user",
                        "content": "请直接通过 function calling 调用 generate_image 工具。",
                    }
                )
                return None
            exec_artifacts = artifacts_from_tool_output(output) if isinstance(output, dict) else []
            exec_jobs: list[dict] = []
            exec_message = str(output.get("message") if isinstance(output, dict) else output) or "已开始生成图片"
            if isinstance(output, dict) and output.get("status") == "pending":
                exec_jobs.append(_pending_job_entry(output.get("generative_job_id", ""), output.get("kind", "image")))
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
    return None


def _dedupe_generative_tool_calls(tool_calls: list, messages: list[dict]) -> list:
    """同一轮内 ``generate_image`` / ``generate_video`` 只保留首次调用。

    避免 LLM 因多张参考图而发起多次 tool_call 导致生成数量翻倍；被合并的调用
    会回一条 tool 消息告知 LLM，否则它会持续重复调用。
    """
    deduplicated: list = []
    seen: set[str] = set()
    for tc in tool_calls:
        slug = tc.function.name
        if slug in _GENERATIVE_SLUGS:
            if slug in seen:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": f"工具 {slug} 已执行，本次重复调用自动合并。",
                    }
                )
                continue
            seen.add(slug)
        deduplicated.append(tc)
    return deduplicated


async def _execute_tool_call(
    tc,
    *,
    tool_executor: ToolExecutor,
    messages: list[dict],
    steps: list[dict],
    artifacts: list[ChatArtifact],
    knowledge_hits: list[dict],
) -> ChatResponse | None:
    """执行单个 tool_call，并把 tool 结果回填 ``messages``。

    返回非 ``None`` 表示应立即结束对话并回复该响应；返回 ``None`` 表示继续
    执行同轮的其他 tool_call。工具元数据解析出非业务异常时按原样抛出。
    """
    slug = tc.function.name
    try:
        args = json.loads(tc.function.arguments or "{}")
    except json.JSONDecodeError:
        args = {}

    try:
        meta = await tool_executor.meta(slug)
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
            answer=(
                f"智能体尝试调用工具「{slug}」，但该工具未找到。\n\n"
                "可能原因：\n"
                "1. 工具 slug 配置有误\n"
                "2. 自定义工具已被删除或禁用\n"
                "3. 内置工具 slug 拼写错误\n\n"
                "请在智能体「能力」步骤中检查 tool_slugs 配置，并确认工具仍在「平台工具」中。"
            ),
            steps=steps,
            artifacts=artifacts,
        )
    except Exception:
        steps.append({"type": "tool_call", "slug": slug, "status": "error", "error": "工具元数据解析失败"})
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
            await tool_executor.invoke(slug, args, confirmed=False)
        except ToolConfirmationSignal as exc:
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
        output = await tool_executor.invoke(slug, args, confirmed=True)
    except ToolConfirmationSignal:
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
        if slug in _GENERATIVE_SLUGS:
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
        job_kind = str(output.get("kind") or "video")
        steps.append(
            {
                "type": "generative_job",
                "slug": slug,
                "job_id": pending_job_id,
                "kind": output.get("kind") or "video",
                "status": "pending",
            }
        )
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
            generative_jobs=[_pending_job_entry(pending_job_id, job_kind)],
        )

    artifacts.extend(artifacts_from_tool_output(output))
    if slug == "knowledge_search" and isinstance(output, dict) and isinstance(output.get("hits"), list):
        knowledge_hits.extend(output["hits"])
    steps.append({"type": "tool_call", "slug": slug, "status": "success"})
    messages.append(
        {
            "role": "tool",
            "tool_call_id": tc.id,
            "content": json.dumps(output, ensure_ascii=False),
        }
    )
    return None


async def run_tool_calling_chat(
    agent: Agent,
    body: ChatRequest,
    *,
    agent_id: UUID,
    system_prompt: str,
    model: ModelConfig,
    usage_sink: UsageSink | None = None,
    tool_executor: ToolExecutor,
    platform_tools: list,
    media_reader: MediaReader,
    kb_ids: list[str] | None = None,
) -> ChatResponse:
    """
    LiteLLM 多轮 function calling 主循环。

    工具 schema 与执行器由 L1 装配后以 ``platform_tools`` / ``tool_executor`` 注入
    （本函数不再查 Tool 表、不直接接触 L1 执行面）；
    流程：按 ``tool_slugs`` 过滤工具 → 多轮 ``acompletion`` →
    ``tool_executor.invoke`` 执行；需确认时抛 ``ToolConfirmationSignal`` 并返回
    ``pending_tool``；``generate_*`` 异步任务返回 ``generative_jobs``；同步附件写入 ``artifacts``。

    ``tool_executor``：L1 注入的执行器（``ToolExecutor`` 契约，见 ``tool_contract``），
    ``meta`` 解析工具元数据、``invoke`` 执行工具（确认信号为 ``ToolConfirmationSignal``）。
    ``media_reader``：L1 注入的媒体读取器（``tenant.attachments.services.media_reader``），
    用于把本轮附图解析为 ``data URL`` multimodal content parts。
    ``kb_ids``：绑定知识库；非空时强制保留 ``knowledge_search`` 工具（不受 ``tool_slugs``
    白名单约束），并把命中片段回填 ``ChatResponse.sources``，实现 RAG 与 tool calling 共存。

    具体职责已下沉：用户确认续接见 ``_resume_confirmed_tool``，正文模拟调用的自救助见
    ``_recover_from_tool_simulation``，单个 tool_call 执行见 ``_execute_tool_call``。
    """
    if not agent.model_config:
        raise ValueError("工具调用需要配置大模型")

    allowed = agent.config.get("tool_slugs") if isinstance(agent.config, dict) else None
    always_allow = {"knowledge_search"} if kb_ids else None
    tools = select_agent_tools(platform_tools, allowed, always_allow=always_allow)
    if allowed and (agent.config or {}).get("skill_package_id"):
        for st in get_skill_bound_tools():
            if st.name not in {t.name for t in tools}:
                tools.append(st)

    if not tools:
        return ChatResponse(
            answer="已启用工具调用，但未找到可用工具。请绑定技能包或在 config.tool_slugs 中配置。",
            steps=[{"type": "tool_agent", "error": "no_tools"}],
        )

    # 用户确认后继续执行挂起的工具
    resumed = await _resume_confirmed_tool(body, tool_executor)
    if resumed is not None:
        return resumed

    openai_tools = _tools_to_openai_schema(tools)
    temperature = float((agent.config or {}).get("temperature", 0.7))
    max_media = int((agent.config or {}).get("max_media_per_turn", 10))
    body_media_count = len(body.media) if body.media else 0
    media_parts = await resolve_media_refs(media_reader, body.media, max_count=max_media) if body.media else []
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
    knowledge_hits: list[dict] = []
    tool_sim_retried = False
    tool_names = [t.name for t in tools]
    tools_by_name = {t.name: t for t in tools}

    if body_media_count > 0 and model.model_type != "vision" and messages_contain_image(messages):
        steps.append(
            {"type": "multimodal_warning", "message": f"当前模型类型为 {model.model_type}（非 vision），图片可能无法被模型识别", "model_type": model.model_type}
        )

    for _ in range(max_iter):
        response = await _litellm_with_tools(model, messages, openai_tools, temperature=temperature)
        if usage_sink is not None:
            p, c, _ = extract_litellm_usage(response)
            await usage_sink.record(prompt_tokens=p, completion_tokens=c)
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []

        if not tool_calls:
            content = getattr(message, "content", None) or ""
            if not tool_sim_retried and _looks_like_tool_call_simulation(content, tool_names):
                tool_sim_retried = True
                recovered = await _recover_from_tool_simulation(
                    content,
                    tool_names=tool_names,
                    tools_by_name=tools_by_name,
                    tool_executor=tool_executor,
                    messages=messages,
                    steps=steps,
                    body=body,
                )
                if recovered is not None:
                    return recovered
                continue
            return ChatResponse(answer=str(content), steps=steps, artifacts=artifacts, sources=knowledge_hits)

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

        # 防重复：同一轮对话中 generate_image / generate_video 只执行首次调用
        for tc in _dedupe_generative_tool_calls(tool_calls, messages):
            terminated = await _execute_tool_call(
                tc,
                tool_executor=tool_executor,
                messages=messages,
                steps=steps,
                artifacts=artifacts,
                knowledge_hits=knowledge_hits,
            )
            if terminated is not None:
                return terminated

    return ChatResponse(
        answer="工具调用达到最大轮次，请简化问题后重试。",
        steps=steps + [{"type": "tool_agent", "error": "max_iterations"}],
        artifacts=artifacts,
        sources=knowledge_hits,
    )
