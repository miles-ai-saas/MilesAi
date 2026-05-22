"""LangChain ChatModel 适配：OpenAI 兼容 HTTP（复用 ModelConfig）。"""

from __future__ import annotations

from typing import Any

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from pydantic import ConfigDict

from app.common.exceptions import AppError
from app.models.model import ModelConfig


def _messages_to_openai(messages: list[BaseMessage]) -> list[dict[str, str]]:
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


def _dict_messages_to_openai(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{"role": m["role"], "content": m["content"]} for m in messages]


async def _http_chat_completion(
    model: ModelConfig,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    api_base = (model.api_base or "https://api.openai.com/v1").rstrip("/")
    url = f"{api_base}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if model.api_key_encrypted:
        headers["Authorization"] = f"Bearer {model.api_key_encrypted}"
    payload = {
        "model": model.model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            raise AppError(f"模型调用失败: {resp.text}", status_code=502)
        data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise AppError("模型返回为空", status_code=502)
    return choices[0]["message"]["content"]


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
        import asyncio

        return asyncio.run(self._agenerate(messages, stop=stop, run_manager=None, **kwargs))

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        openai_msgs = _messages_to_openai(messages)
        content = await _http_chat_completion(
            self.model_row,
            openai_msgs,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        gen = ChatGeneration(message=AIMessage(content=content))
        return ChatResult(generations=[gen])


def get_chat_model(
    model: ModelConfig,
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> PlatformChatModel:
    return PlatformChatModel(
        model_row=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def ainvoke_chat(
    model: ModelConfig,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    db: Any | None = None,
    tenant_id: Any | None = None,
) -> str:
    """异步对话（dict messages），供业务层统一调用。"""
    if db is not None and tenant_id is not None:
        from uuid import UUID

        from app.app_tenant.models.services.model_resolve import resolve_model_for_invoke

        model = await resolve_model_for_invoke(db, model, UUID(str(tenant_id)))
    llm = get_chat_model(model, temperature=temperature, max_tokens=max_tokens)
    from langchain_core.messages import HumanMessage, SystemMessage

    lc_messages: list[BaseMessage] = []
    for m in messages:
        role, content = m.get("role", "user"), m.get("content", "")
        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))
        else:
            lc_messages.append(HumanMessage(content=content))
    result = await llm.ainvoke(lc_messages)
    return result.content if isinstance(result.content, str) else str(result.content)
