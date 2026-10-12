"""LangChain ``StructuredTool`` 与 LiteLLM/OpenAI function calling 的桥接。

职责
----
- 把 ``StructuredTool`` 的 name/description/args_schema 转成 OpenAI ``tools`` 数组；
- 封装带 ``tools`` / ``tool_choice=auto`` 的 ``litellm.acompletion`` 调用；
- 可选 ``on_delta``：流式路径上把 content token 推给调用方（tool_call 轮通常无正文）。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import litellm

from miles_integrations.litellm.adapter import (
    OnDelta,
    _ensure_messages_valid_for_chat,
    _extract_stream_delta_content,
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


def _completion_kwargs(
    model,
    messages: list[dict],
    tools: list[dict],
    *,
    temperature: float,
    stream: bool,
) -> dict[str, Any]:
    """构造 ``acompletion`` 公共参数。"""
    _ensure_messages_valid_for_chat(model, messages)
    kwargs: dict[str, Any] = {
        "model": resolve_litellm_model(model),
        "messages": messages,
        "temperature": temperature,
        "tools": tools,
        "tool_choice": "auto",
    }
    if stream:
        kwargs["stream"] = True
    if model.api_key_encrypted:
        kwargs["api_key"] = model.api_key_encrypted
    api_base = _resolve_api_base(model)
    if api_base:
        kwargs["api_base"] = api_base
    return kwargs


def _extract_stream_tool_call_deltas(chunk: Any) -> list[Any]:
    """从流式 chunk 取出 ``delta.tool_calls``（对象或 dict 均可）。"""
    choices = getattr(chunk, "choices", None) or []
    if not choices:
        return []
    first = choices[0]
    delta = getattr(first, "delta", None)
    if delta is None and isinstance(first, dict):
        delta = first.get("delta")
    if delta is None:
        return []
    tool_calls = getattr(delta, "tool_calls", None)
    if tool_calls is None and isinstance(delta, dict):
        tool_calls = delta.get("tool_calls")
    return list(tool_calls or [])


def _merge_tool_call_delta(acc: dict[int, dict[str, Any]], raw: Any) -> None:
    """按 index 合并流式 tool_call 片段。"""
    if isinstance(raw, dict):
        index = int(raw.get("index") or 0)
        entry = acc.setdefault(
            index,
            {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
        )
        if raw.get("id"):
            entry["id"] = str(raw["id"])
        if raw.get("type"):
            entry["type"] = str(raw["type"])
        fn = raw.get("function") or {}
        if isinstance(fn, dict):
            if fn.get("name"):
                entry["function"]["name"] = str(fn["name"])
            if fn.get("arguments"):
                entry["function"]["arguments"] += str(fn["arguments"])
        return

    index = int(getattr(raw, "index", 0) or 0)
    entry = acc.setdefault(
        index,
        {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
    )
    call_id = getattr(raw, "id", None)
    if call_id:
        entry["id"] = str(call_id)
    call_type = getattr(raw, "type", None)
    if call_type:
        entry["type"] = str(call_type)
    fn = getattr(raw, "function", None)
    if fn is None:
        return
    name = getattr(fn, "name", None) if not isinstance(fn, dict) else fn.get("name")
    arguments = getattr(fn, "arguments", None) if not isinstance(fn, dict) else fn.get("arguments")
    if name:
        entry["function"]["name"] = str(name)
    if arguments:
        entry["function"]["arguments"] += str(arguments)


def _tool_calls_from_acc(acc: dict[int, dict[str, Any]]) -> list[SimpleNamespace]:
    """合并结果 → 与非流式 ``message.tool_calls`` 同形的简易对象列表。"""
    out: list[SimpleNamespace] = []
    for index in sorted(acc):
        item = acc[index]
        fn = item["function"]
        if not fn.get("name"):
            continue
        out.append(
            SimpleNamespace(
                id=item.get("id") or f"call-{index}",
                type=item.get("type") or "function",
                function=SimpleNamespace(name=fn["name"], arguments=fn.get("arguments") or "{}"),
            )
        )
    return out


def _response_from_parts(
    content: str,
    tool_calls: list[SimpleNamespace],
    *,
    usage: Any | None = None,
) -> SimpleNamespace:
    """组装与非流式 ``acompletion`` 兼容的响应壳，供主循环继续解析。"""
    message = SimpleNamespace(content=content, tool_calls=tool_calls or None)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=usage)


async def _litellm_with_tools_stream(
    model,
    messages: list[dict],
    tools: list[dict],
    *,
    temperature: float,
    on_delta: OnDelta | None,
) -> Any:
    """流式 function calling：content token 经 ``on_delta`` 推送；tool_call 轮通常无正文。"""
    kwargs = _completion_kwargs(model, messages, tools, temperature=temperature, stream=True)
    response = await litellm.acompletion(**kwargs)

    content_parts: list[str] = []
    tool_acc: dict[int, dict[str, Any]] = {}
    usage: Any | None = None

    async for chunk in response:
        piece = _extract_stream_delta_content(chunk)
        if piece:
            content_parts.append(piece)
            if on_delta is not None:
                await on_delta(piece)
        for raw in _extract_stream_tool_call_deltas(chunk):
            _merge_tool_call_delta(tool_acc, raw)
        chunk_usage = getattr(chunk, "usage", None)
        if chunk_usage is None and isinstance(chunk, dict):
            chunk_usage = chunk.get("usage")
        if chunk_usage is not None:
            usage = chunk_usage

    tool_calls = _tool_calls_from_acc(tool_acc)
    # tool 轮若偶发夹带正文 delta，主循环不会把它当最终答案；WS 已推送的短片段可接受
    return _response_from_parts("".join(content_parts), tool_calls, usage=usage)


async def _litellm_with_tools(
    model,
    messages: list[dict],
    tools: list[dict],
    *,
    temperature: float,
    on_delta: OnDelta | None = None,
) -> Any:
    """带 ``tools`` / ``tool_choice=auto`` 的 LiteLLM ``acompletion`` 封装。

    ``on_delta`` 非空时走流式路径，把 content token 推给调用方（最终回答真流式）；
    中间 tool_call 轮通常无正文，行为与非流式一致。
    """
    if on_delta is not None:
        return await _litellm_with_tools_stream(
            model,
            messages,
            tools,
            temperature=temperature,
            on_delta=on_delta,
        )
    kwargs = _completion_kwargs(model, messages, tools, temperature=temperature, stream=False)
    return await litellm.acompletion(**kwargs)
