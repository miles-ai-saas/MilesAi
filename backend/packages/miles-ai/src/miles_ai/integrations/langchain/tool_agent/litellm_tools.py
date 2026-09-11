"""LangChain ``StructuredTool`` 与 LiteLLM/OpenAI function calling 的桥接。

职责
----
- 把 ``StructuredTool`` 的 name/description/args_schema 转成 OpenAI ``tools`` 数组；
- 封装带 ``tools`` / ``tool_choice=auto`` 的 ``litellm.acompletion`` 调用。
"""

from __future__ import annotations

from typing import Any

import litellm

from miles_ai.integrations.litellm.adapter import (
    _ensure_messages_valid_for_chat,
    _resolve_api_base,
    resolve_litellm_model,
)


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
