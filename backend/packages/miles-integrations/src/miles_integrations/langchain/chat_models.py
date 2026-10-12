"""
LangChain ChatModel 适配：平台 ModelConfig → LiteLLM 对话。

业务入口（优先 ``ainvoke_chat``）
-------------------------------
- ``AgentService._direct_chat`` / ``_rag_chat`` / LangGraph ``generate`` / ``fallback``
- ``rag.generate.generate_rag_answer``
- ``flow_runtime.nodes.llm_nodes.llm_call``
- ``tool_agent`` 多轮 function calling

``ainvoke_chat`` 要求调用方先 resolve 模型（合并 BYOK）；用量经 ``usage_sink`` 注入。
``PlatformChatModel`` 供需要 LangChain Runnable 链的场景；多数路径直接用 ``ainvoke_chat``。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import ConfigDict

from miles_common.exceptions import AppError, BadRequestError
from miles_core.models.model import ModelConfig
from miles_integrations.litellm.adapter import (
    _ensure_messages_valid_for_chat,
    _extract_stream_delta_content,
    _litellm_error_message,
    _resolve_api_base,
    litellm_chat_completion,
    litellm_chat_completion_stream,
    resolve_litellm_model,
)
from miles_integrations.litellm.usage_sink import UsageSink

OnDelta = Callable[[str], Awaitable[None]]


def _messages_to_openai(messages: list[BaseMessage]) -> list[dict[str, str]]:
    """LangChain Message → OpenAI chat messages 格式。"""
    out: list[dict[str, str]] = []
    for m in messages:
        role = "user"
        if m.type == "system":
            role = "system"
        elif m.type == "ai":
            role = "assistant"
        elif m.type == "human":
            role = "user"
        content = m.content if isinstance(m.content, str) else str(m.content)
        out.append({"role": role, "content": content})
    return out


class PlatformChatModel(BaseChatModel):
    """将平台 ModelConfig 暴露为 LangChain BaseChatModel。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model_row: ModelConfig
    temperature: float = 0.7
    max_tokens: int = 2048

    @property
    def _llm_type(self) -> str:
        return f"platform-{self.model_row.provider}"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """同步入口：内部 asyncio.run 调异步实现。"""
        import asyncio

        return asyncio.run(self._agenerate(messages, stop=stop, run_manager=None, **kwargs))

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """LangChain 异步生成：委托 litellm_chat_completion。"""
        openai_msgs = _messages_to_openai(messages)
        content = await litellm_chat_completion(
            self.model_row,
            openai_msgs,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        gen = ChatGeneration(message=AIMessage(content=content))
        return ChatResult(generations=[gen])

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        """LangChain 异步流式：LiteLLM ``stream=True``，供 DeepAgents / LangGraph ``astream``。"""
        import litellm

        openai_msgs = _messages_to_openai(messages)
        _ensure_messages_valid_for_chat(self.model_row, openai_msgs)
        call_kw: dict[str, Any] = {
            "model": resolve_litellm_model(self.model_row),
            "messages": openai_msgs,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        if self.model_row.api_key_encrypted:
            call_kw["api_key"] = self.model_row.api_key_encrypted
        api_base = _resolve_api_base(self.model_row)
        if api_base:
            call_kw["api_base"] = api_base
        try:
            response = await litellm.acompletion(**call_kw)
        except BadRequestError:
            raise
        except Exception as exc:
            raise AppError(_litellm_error_message(exc), status_code=502) from exc

        async for chunk in response:
            piece = _extract_stream_delta_content(chunk)
            if not piece:
                continue
            if run_manager:
                await run_manager.on_llm_new_token(piece)
            yield ChatGenerationChunk(message=AIMessageChunk(content=piece))


def get_chat_model(
    model: ModelConfig,
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> PlatformChatModel:
    """构建 LangChain BaseChatModel 实例。"""
    return PlatformChatModel(
        model_row=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def ainvoke_chat(
    model: ModelConfig,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    usage_sink: UsageSink | None = None,
    on_delta: OnDelta | None = None,
) -> str:
    """
    异步对话（OpenAI 形状 ``{"role","content"}`` 列表）。

    ``model`` 须为调用方已解析（合并 BYOK）的配置；用量记录经
    ``usage_sink`` 注入（见 ``litellm.usage_sink.UsageSink``）。
    ``content`` 可为字符串或多模态 part 数组（见 ``integrations.chat.multimodal``）。
    """
    openai_msgs: list[dict[str, Any]] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        openai_msgs.append({"role": role, "content": content})
    if on_delta is not None:
        return await litellm_chat_completion_stream(
            model,
            openai_msgs,
            temperature=temperature,
            max_tokens=max_tokens,
            usage_sink=usage_sink,
            on_delta=on_delta,
        )
    return await litellm_chat_completion(
        model,
        openai_msgs,
        temperature=temperature,
        max_tokens=max_tokens,
        usage_sink=usage_sink,
    )


def dict_messages_to_lc(messages: list[dict[str, str]]) -> list[BaseMessage]:
    """dict messages → LangChain messages（供需要 LC 对象的调用方）。"""
    lc_messages: list[BaseMessage] = []
    for m in messages:
        role, content = m.get("role", "user"), m.get("content", "")
        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))
        else:
            lc_messages.append(HumanMessage(content=content))
    return lc_messages
