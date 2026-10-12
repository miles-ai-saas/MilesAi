"""LiteLLM 多轮 function calling 主循环（工具 schema 与执行器由 L1 装配注入）。"""

from __future__ import annotations

from miles_core.models.agent import Agent
from miles_core.models.agent.chat_io import ChatArtifact, ChatRequest, ChatResponse
from miles_core.models.media.reader import MediaReader
from miles_core.models.model import ModelConfig
from miles_integrations.chat.multimodal import build_user_message, messages_contain_image, resolve_media_refs
from miles_integrations.langchain.tool_agent.confirm import (
    _ConfirmedToolSeed,
    _recover_from_tool_simulation,
    _resume_confirmed_tool,
    _seed_confirmed_tool_messages,
)
from miles_integrations.langchain.tool_agent.execute import (
    _assistant_tool_call_message,
    _dedupe_generative_tool_calls,
    _execute_tool_call,
)
from miles_integrations.langchain.tool_agent.litellm_tools import (
    _litellm_with_tools,
    _tools_to_openai_schema,
)
from miles_integrations.langchain.tool_agent.parse import _looks_like_tool_call_simulation
from miles_integrations.langchain.tool_agent.tool_contract import ToolExecutor
from miles_integrations.langchain.toolkit.catalog import bound_skill_ids, get_skill_bound_tools
from miles_integrations.langchain.toolkit.naming import select_agent_tools
from miles_integrations.litellm.adapter import OnDelta, extract_litellm_usage
from miles_integrations.litellm.usage_sink import UsageSink


async def run_tool_calling_chat(
    agent: Agent,
    body: ChatRequest,
    *,
    system_prompt: str,
    model: ModelConfig,
    usage_sink: UsageSink | None = None,
    tool_executor: ToolExecutor,
    platform_tools: list,
    media_reader: MediaReader,
    kb_ids: list[str] | None = None,
    history_messages: list[dict] | None = None,
    on_delta: OnDelta | None = None,
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
    ``history_messages``：服务端从 PG 加载并截断后的跨轮 user/assistant（不含本轮）。
    ``on_delta``：非空时每轮 LLM 走流式；最终回答 content token 真推送（WS/A2A）；
    tool_call 轮通常无正文。

    具体职责已下沉：用户确认续接见 ``_resume_confirmed_tool``（同步成功后注入 messages
    继续 LLM，``on_delta`` 真流），正文模拟调用的自救助见 ``_recover_from_tool_simulation``，
    单个 tool_call 执行见 ``_execute_tool_call``。
    """
    if not agent.model_config:
        raise ValueError("工具调用需要配置大模型")

    allowed = agent.config.get("tool_slugs") if isinstance(agent.config, dict) else None
    always_allow = {"knowledge_search"} if kb_ids else None
    tools = select_agent_tools(platform_tools, allowed, always_allow=always_allow)
    if allowed and bound_skill_ids(agent.config):
        for st in get_skill_bound_tools():
            if st.name not in {t.name for t in tools}:
                tools.append(st)

    if not tools:
        return ChatResponse(
            answer="已启用工具调用，但未找到可用工具。请绑定技能包或在 config.tool_slugs 中配置。",
            steps=[{"type": "tool_agent", "error": "no_tools"}],
        )

    # 用户确认后：终态（失败 / 异步 job）直接返回；同步成功则 seed 后进入下方 LLM 循环
    resumed = await _resume_confirmed_tool(body, tool_executor)
    if isinstance(resumed, ChatResponse):
        return resumed

    openai_tools = _tools_to_openai_schema(tools)
    temperature = float((agent.config or {}).get("temperature", 0.7))
    max_media = int((agent.config or {}).get("max_media_per_turn", 10))
    body_media_count = len(body.media) if body.media else 0
    media_parts = await resolve_media_refs(media_reader, body.media, max_count=max_media) if body.media else []
    chat_query = body.query.strip() or ("请根据附图回答。" if media_parts else body.query)
    user_msg = build_user_message(query=chat_query, media_parts=media_parts)
    prior = list(history_messages or [])
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        *prior,
        user_msg,
    ]
    max_iter = int((agent.config or {}).get("max_tool_iterations", 5))
    steps: list[dict] = [
        {
            "type": "tool_agent",
            "engine": "litellm_tools",
            "media_count": body_media_count,
            "media_resolved": len(media_parts),
            "model_type": model.model_type,
            "history_messages": len(prior),
        }
    ]
    artifacts: list[ChatArtifact] = []
    knowledge_hits: list[dict] = []
    if isinstance(resumed, _ConfirmedToolSeed):
        artifacts.extend(resumed.artifacts)
        knowledge_hits.extend(resumed.knowledge_hits)
        steps.extend(resumed.steps)
        _seed_confirmed_tool_messages(messages, resumed)
    tool_sim_retried = False
    tool_names = [t.name for t in tools]
    tools_by_name = {t.name: t for t in tools}

    if body_media_count > 0 and model.model_type != "vision" and messages_contain_image(messages):
        steps.append(
            {"type": "multimodal_warning", "message": f"当前模型类型为 {model.model_type}（非 vision），图片可能无法被模型识别", "model_type": model.model_type}
        )

    for _ in range(max_iter):
        response = await _litellm_with_tools(
            model,
            messages,
            openai_tools,
            temperature=temperature,
            on_delta=on_delta,
        )
        if usage_sink is not None:
            p, c, _ = extract_litellm_usage(response)
            await usage_sink.record(prompt_tokens=p, completion_tokens=c)
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []

        if not tool_calls:
            content = getattr(message, "content", None) or ""
            # 模型偶尔把工具调用写进正文；仅在首次出现时尝试自救助，救不回来则按普通回复收束
            if tool_sim_retried or not _looks_like_tool_call_simulation(content, tool_names):
                return ChatResponse(answer=str(content), steps=steps, artifacts=artifacts, sources=knowledge_hits)
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

        messages.append(_assistant_tool_call_message(message, tool_calls))

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
