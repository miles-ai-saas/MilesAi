"""
智能体工具调用循环（无知识库绑定时可选）。

当 ``AgentService._rag_chat`` 无 ``kb_ids`` 且 ``config.enable_tool_calling`` 为真时启用：
LiteLLM function calling + 平台内置工具（``integrations.langchain.tools``）+ 人工确认策略。

有 KB 时：若 ``enable_generative_tools`` 和/或绑定技能包且 ``enable_tool_calling``，
走本模块（``knowledge_search`` + 可选 generate_*）；否则走 LangGraph/线性 RAG。
"""

from __future__ import annotations

import ast
import json
import re
from typing import Any
from uuid import UUID

import litellm
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError
from app.core.tenant import TenantContext
from app.integrations.chat.multimodal import build_user_message, messages_contain_image, resolve_media_refs
from app.integrations.langchain.tools import get_all_platform_tools, get_skill_bound_tools
from app.integrations.litellm.adapter import (
    _ensure_chat_model_type,
    _ensure_messages_valid_for_chat,
    _resolve_api_base,
    resolve_litellm_model,
)
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


# 生图/生视频参数特征字段，用于判断 LLM 是否把参数 JSON 输出到正文了
_GENERATIVE_PARAM_KEYS = frozenset(
    {
        "prompt",
        "size",
        "n",
        "duration",
        "resolution",
        "image_attachment_id",
        "model_config_id",
    }
)

# LLM 输出中表示"我想生图但没有正确调用 tool"的意图短语
_GENERATIVE_INTENT_PHRASES = frozenset(
    {
        "正在为您生成",
        "正在生成图片",
        "正在生成图像",
        "开始生图",
        "开始生成",
        "为您生成图片",
        "正在创作",
        "正在绘制",
        "图片生成中",
        "图像生成中",
    }
)

# 从文本中提取 JSON 对象的模式（匹配最外层 { ... }，支持嵌套）
_JSON_OBJECT_PATTERN = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)

# 合法 UUID 格式
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

# 需要校验 UUID 格式的参数名
_UUID_PARAM_NAMES = frozenset({"model_config_id", "image_attachment_id", "last_frame_attachment_id"})


def _clean_uuid_params(params: dict) -> dict:
    """剔除参数中非 UUID 格式的值（如 "taobao-product"、"ref1" 等占位符），
    避免下游 UUID() 构造崩溃。"""
    cleaned = dict(params)
    for key in _UUID_PARAM_NAMES:
        val = cleaned.get(key)
        if isinstance(val, str) and not _UUID_RE.match(val):
            del cleaned[key]
    return cleaned


def _looks_like_tool_call_simulation(content: Any, tool_names: list[str]) -> bool:
    """检测 LLM 响应内容是否在文字中模拟了工具调用（而非真正发起 tool_call）。

    覆盖以下盲区：
    - 裸 JSON 如 ``{"prompt": "...", "size": "1024x1024"}``（无工具名、无中文提示）
    - 函数式写法 ``generate_image({"prompt": "..."})``（缺少 "function" 关键词）
    - OpenAI function call 格式 ``{"function": "generate_image", "arguments": {..."prompt":..."}}``——参数嵌套在 arguments 内
    - 代码块内的 JSON 参数（无中文提示词）
    - 文本中混杂的 JSON 参数（如 "好的，参数如下：{"prompt": "xxx"}"）
    """
    if not isinstance(content, str) or not content:
        return False
    content_stripped = content.strip()
    tool_mentioned = any(name in content_stripped for name in tool_names)

    # 情况 A: 输出中提到了工具名
    if tool_mentioned:
        # A1: 带代码块的 JSON
        if re.search(r"```(?:json)?\s*\{", content_stripped, re.DOTALL):
            return True
        # A2: 类似 "generate_image({\"prompt\": ...})" 的直接调用写法
        tool_call_like = any(
            re.search(rf"{re.escape(name)}\s*\(", content_stripped) for name in tool_names
        )
        if tool_call_like:
            return True
        # A3: 输出含 "function"+"arguments"/"params" 键——典型的 function call JSON
        #     无论是否有中文提示，都应拦截
        has_function_args = '"function"' in content_stripped and (
            '"arguments"' in content_stripped or '"params"' in content_stripped
        )
        if has_function_args:
            return True

    # 情况 B: 输出中包含长得像生图/生视频参数的 JSON 对象
    json_candidates = _JSON_OBJECT_PATTERN.findall(content_stripped)
    for candidate in json_candidates:
        try:
            parsed = json.loads(candidate)
            if not isinstance(parsed, dict):
                continue
            # B1: 顶层就有生图参数（如裸 {"prompt": "...", "size": "1024x1024"}）
            if any(k in parsed for k in _GENERATIVE_PARAM_KEYS):
                return True
            # B2: 参数嵌套在 "arguments" 内（如 {"function": "generate_image", "arguments": {...}}）
            inner_args = parsed.get("arguments")
            if isinstance(inner_args, dict) and any(k in inner_args for k in _GENERATIVE_PARAM_KEYS):
                return True
        except (json.JSONDecodeError, TypeError):
            pass

    # 情况 C: 输出中包含"生成意图"短语（如"正在为您生成图片…"），但没有 JSON 参数
    #           说明 LLM 有意生图但不会用 tool_calls，需要兜底处理
    if any(phrase in content_stripped for phrase in _GENERATIVE_INTENT_PHRASES):
        return True

    return False


# ---------------------------------------------------------------------------
# Python kwargs 解析：用 ast 替代正则，天然覆盖所有 Python 字面量语法
# ---------------------------------------------------------------------------

def _parse_as_python_kwargs(params_text: str) -> dict[str, Any] | None:
    """通过构造 ``_dummy(key=..., ...)`` 并用 ``ast`` 解析，
    可靠提取 Python 风格关键字参数，无需手写正则。"""
    source = f"_dummy({params_text})"
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    if not tree.body:
        return None
    call = tree.body[0].value
    if not isinstance(call, ast.Call):
        return None
    result: dict[str, Any] = {}
    for kw in call.keywords:
        try:
            result[kw.arg] = ast.literal_eval(kw.value)
        except (ValueError, TypeError):
            result[kw.arg] = ast.unparse(kw.value)
    return result if result else None


def _get_schema_for(tools_by_name: dict[str, Any], tool_name: str) -> type | None:
    """从工具名查找 Pydantic args_schema 类。"""
    tool = tools_by_name.get(tool_name)
    if tool is None or not hasattr(tool, "args_schema"):
        return None
    schema = tool.args_schema
    return type(schema) if schema is not None else None


def _validate_and_clean(
    params: dict[str, Any],
    tools_by_name: dict[str, Any],
    tool_name: str,
) -> dict[str, Any]:
    """清理 UUID + 用工具 schema 校验/转换，schema 失败时保留原始提取结果。"""
    cleaned = _clean_uuid_params(params)
    schema_cls = _get_schema_for(tools_by_name, tool_name)
    if schema_cls is None:
        return cleaned
    try:
        return schema_cls(**cleaned).model_dump(exclude_unset=False)
    except Exception:
        return cleaned


# ---------------------------------------------------------------------------
# 从 LLM 文本输出中提取工具调用信息
# ---------------------------------------------------------------------------

def _extract_tool_params_from_text(
    content: str,
    tools_by_name: dict[str, Any],
) -> tuple[str, dict] | None:
    """从 LLM 文本中提取工具名 + 参数，支持以下格式：

    - ``generate_image(prompt="...", size="...", n=1)``    ← Python kwargs（ast 解析 → schema 校验）
    - ``generate_image({"prompt": ..., "size": ...})``     ← JSON 内嵌 → schema 校验
    - ``{"tool": "generate_image", ...}``                  ← tool-keyed JSON
    - ``{"function": "generate_image", "arguments": {...}}`` ← OpenAI-style
    - 裸 ``{"prompt": "...", "size": "1024x1024"}``       ← 按参数特征推断工具名
    """
    tool_names = list(tools_by_name.keys())
    clean = re.sub(r"```(?:json|python)?\s*", "", content).strip("` \n\r\t")

    # 1) tool_name( ... ) —— 平衡括号匹配 → JSON / ast kwargs
    for name in sorted(set(tool_names), key=len, reverse=True):
        m = re.search(rf"\b{re.escape(name)}\s*\(", clean)
        if not m:
            continue
        body_start = m.end()
        depth, body_end = 1, body_start
        for i, ch in enumerate(clean[body_start:], body_start):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    body_end = i
                    break
        body = clean[body_start:body_end].strip()
        # JSON 优先
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                return name, _validate_and_clean(parsed, tools_by_name, name)
        except (json.JSONDecodeError, TypeError):
            pass
        # 回退 ast kwargs
        kwargs = _parse_as_python_kwargs(body)
        if kwargs:
            return name, _validate_and_clean(kwargs, tools_by_name, name)

    # 2) 独立 JSON 对象（无工具名前缀）
    for candidate in _JSON_OBJECT_PATTERN.findall(clean):
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(parsed, dict):
            continue

        # {"tool": "generate_image", ...}
        tool_key = parsed.get("tool")
        if isinstance(tool_key, str) and tool_key in tools_by_name:
            params = {k: v for k, v in parsed.items() if k != "tool"}
            return tool_key, _validate_and_clean(params, tools_by_name, tool_key)

        # {"function": "generate_image", "arguments": {...}}
        func = parsed.get("function")
        if isinstance(func, str) and func in tools_by_name:
            inner = parsed.get("arguments")
            params = inner if isinstance(inner, dict) else {k: v for k, v in parsed.items() if k != "function"}
            return func, _validate_and_clean(params, tools_by_name, func)

        # 裸参数 → 按特征推断工具名
        if any(k in parsed for k in _GENERATIVE_PARAM_KEYS):
            has_video = "duration" in parsed or "resolution" in parsed
            for n in tool_names:
                if has_video and "video" in n:
                    return n, _validate_and_clean(parsed, tools_by_name, n)
                if not has_video and "image" in n and "video" not in n:
                    return n, _validate_and_clean(parsed, tools_by_name, n)
            return tool_names[0], _validate_and_clean(parsed, tools_by_name, tool_names[0])

    return None


def _artifacts_from_tool_output(output: dict) -> list[ChatArtifact]:
    """将 invoke 返回的 generate_* 字典转为 ChatArtifact（供前端预览）。"""
    if not isinstance(output, dict):
        return []
    kind = str(output.get("kind") or "image")
    status = output.get("status")
    job_id = output.get("generative_job_id") or output.get("job_id")
    job_id_str = str(job_id) if job_id else None

    if status == "pending" and job_id_str:
        return [
            ChatArtifact(
                kind=kind if kind in ("image", "video") else "video",
                status="pending",
                job_id=job_id_str,
                caption=output.get("message"),
                progress_message=output.get("progress_message") or output.get("message"),
            )
        ]

    if status == "failed":
        return [
            ChatArtifact(
                kind=kind if kind in ("image", "video") else "image",
                status="failed",
                job_id=job_id_str,
                error_message=str(output.get("error_message") or output.get("message") or "生成失败"),
                caption=output.get("message"),
            )
        ]

    def _uuid_or_none(v) -> UUID | None:
        if v is None or v == "":
            return None
        return UUID(str(v))

    if kind == "image":
        ids = output.get("attachment_ids") or []
        if not ids and output.get("attachment_id"):
            ids = [output["attachment_id"]]
        mids = output.get("media_asset_ids") or []
        if not mids and output.get("media_asset_id"):
            mids = [output["media_asset_id"]]
        mime = output.get("mime_type")
        return [
            ChatArtifact(
                attachment_id=_uuid_or_none(aid),
                kind="image",
                mime_type=mime,
                caption=output.get("message"),
                status="success",
                job_id=job_id_str,
                media_asset_id=_uuid_or_none(mids[i] if i < len(mids) else (mids[0] if mids else None)),
            )
            for i, aid in enumerate(ids)
            if aid
        ]
    if kind == "video" and output.get("attachment_id"):
        return [
            ChatArtifact(
                attachment_id=UUID(str(output["attachment_id"])),
                kind="video",
                mime_type=output.get("mime_type") or "video/mp4",
                caption=output.get("message"),
                status="success",
                job_id=job_id_str,
                media_asset_id=_uuid_or_none(output.get("media_asset_id")),
            )
        ]
    return []


def _tools_to_openai_schema(tools: list) -> list[dict]:
    """StructuredTool → LiteLLM/OpenAI ``tools`` 数组（name、description、parameters JSON Schema）。"""
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
    """带 ``tools`` / ``tool_choice=auto`` 的 LiteLLM ``acompletion`` 封装。"""
    _ensure_messages_valid_for_chat(model, messages)
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
            confirm_artifacts = _artifacts_from_tool_output(output) if isinstance(output, dict) else []
            confirm_message = str(output.get("message") if isinstance(output, dict) else output)
            confirm_jobs: list[dict] = []
            if isinstance(output, dict) and output.get("status") == "pending":
                confirm_jobs.append({
                    "id": output.get("generative_job_id", ""),
                    "kind": output.get("kind", "image"),
                    "status": "pending",
                })
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
    steps: list[dict] = [{"type": "tool_agent", "engine": "litellm_tools", "media_count": body_media_count, "media_resolved": len(media_parts), "model_type": model.model_type}]
    artifacts: list[ChatArtifact] = []
    _tool_sim_retried = False
    _tool_names = [t.name for t in tools]
    _tools_by_name = {t.name: t for t in tools}

    if body_media_count > 0 and model.model_type != "vision" and messages_contain_image(messages):
        steps.append({"type": "multimodal_warning", "message": f"当前模型类型为 {model.model_type}（非 vision），图片可能无法被模型识别", "model_type": model.model_type})

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
                                db, ctx, slug, params,
                                confirmed=True,
                                agent_id=agent_id,
                                actor_user_id=ctx.user_id,
                                invoke_source="agent",
                            )
                        except Exception as exc:
                            steps.append({"type": "tool_simulation_corrected", "message": f"提取 JSON 参数后执行 {slug} 失败: {exc}，追加纠正提示"})
                            messages.append({"role": "assistant", "content": content})
                            messages.append({
                                "role": "user",
                                "content": (
                                    "你刚才输出的 JSON 无法被系统正确解析执行。"
                                    "请直接通过 function calling 机制（tool_use）调用工具，"
                                    "而不是在文字中输出 JSON 参数。"
                                    "如需生图，请发起真正的 tool_call。"
                                ),
                            })
                            continue
                        exec_artifacts = _artifacts_from_tool_output(output) if isinstance(output, dict) else []
                        exec_jobs: list[dict] = []
                        exec_message = str(output.get("message") if isinstance(output, dict) else output) or f"已执行工具 {slug}"
                        if isinstance(output, dict) and output.get("status") == "pending":
                            exec_jobs.append({
                                "id": output.get("generative_job_id", ""),
                                "kind": output.get("kind", "image"),
                                "status": "pending",
                            })
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
                                db, ctx, image_tool, {"prompt": fallback_query},
                                confirmed=True,
                                agent_id=agent_id,
                                actor_user_id=ctx.user_id,
                                invoke_source="agent",
                            )
                        except Exception as exc:
                            steps.append({"type": "tool_simulation_corrected", "message": f"用原始 query 兜底执行 {image_tool} 失败: {exc}"})
                            messages.append({"role": "assistant", "content": content})
                            messages.append({
                                "role": "user",
                                "content": "请直接通过 function calling 调用 generate_image 工具。",
                            })
                            continue
                        exec_artifacts = _artifacts_from_tool_output(output) if isinstance(output, dict) else []
                        exec_jobs: list[dict] = []
                        exec_message = str(output.get("message") if isinstance(output, dict) else output) or "已开始生成图片"
                        if isinstance(output, dict) and output.get("status") == "pending":
                            exec_jobs.append({
                                "id": output.get("generative_job_id", ""),
                                "kind": output.get("kind", "image"),
                                "status": "pending",
                            })
                        steps.append({"type": "tool_simulation_intent_fallback", "slug": image_tool, "message": f"LLM 表达了生成意图但无 JSON，用原始 query 作为 prompt 兜底执行", "fallback_query_preview": fallback_query[:200]})
                        return ChatResponse(
                            answer=exec_message,
                            steps=steps,
                            artifacts=exec_artifacts,
                            generative_jobs=exec_jobs,
                        )
                # 其他提取失败：回退到纠正提示重试
                steps.append({"type": "tool_simulation_corrected", "message": "LLM 在文字中模拟了工具调用，已追加纠正提示"})
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": (
                        "你刚才在文字中描述了工具调用，但并未真正发起 function call。"
                        "请直接通过 tool_use 机制调用工具，不要用文字描述调用过程。"
                        "如需生图，立即调用 generate_image 工具并传入参数。"
                    ),
                })
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
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": f"工具 {slug} 已执行，本次重复调用自动合并。",
                    })
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
                artifacts.extend(_artifacts_from_tool_output(pending_out))
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
