"""tool_agent 流式：最终回答透传 on_delta；tool_call 轮组装 tool_calls。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from miles_core.models.agent.chat_io import ChatRequest
from miles_integrations.langchain.tool_agent import litellm_tools as tools_mod
from miles_integrations.langchain.tool_agent import loop as loop_mod


class _Tool:
    def __init__(self, name: str) -> None:
        self.name = name
        self.description = name
        self.args_schema = None


class _Executor:
    async def meta(self, slug, *, tool_id=None):  # noqa: ANN001
        return {"slug": slug, "name": slug, "require_confirmation": False}

    async def invoke(self, slug, params, *, confirmed=False, tool_id=None):  # noqa: ANN001
        return {"message": f"{slug} ok", "hits": [{"text": "hit"}]}


def _agent():
    return SimpleNamespace(
        model_config=object(),
        config={"enable_tool_calling": True, "tool_slugs": ["calculator"], "max_tool_iterations": 3},
    )


@pytest.mark.asyncio
async def test_final_answer_forwards_on_delta(monkeypatch):
    deltas: list[str] = []

    async def fake(model, messages, tools, *, temperature, on_delta=None):  # noqa: ANN001
        assert on_delta is not None
        await on_delta("你")
        await on_delta("好")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="你好", tool_calls=None))],
            usage=None,
        )

    monkeypatch.setattr(loop_mod, "_litellm_with_tools", fake)

    async def on_delta(text: str) -> None:
        deltas.append(text)

    resp = await loop_mod.run_tool_calling_chat(
        _agent(),
        ChatRequest(query="hi"),
        system_prompt="sys",
        model=SimpleNamespace(model_type="chat"),
        tool_executor=_Executor(),
        platform_tools=[_Tool("calculator")],
        media_reader=None,
        on_delta=on_delta,
    )
    assert resp.answer == "你好"
    assert deltas == ["你", "好"]


@pytest.mark.asyncio
async def test_merge_stream_tool_call_deltas():
    acc: dict[int, dict] = {}
    tools_mod._merge_tool_call_delta(
        acc,
        {"index": 0, "id": "call-1", "type": "function", "function": {"name": "calculator", "arguments": ""}},
    )
    tools_mod._merge_tool_call_delta(acc, {"index": 0, "function": {"arguments": '{"expression":"1+1"}'}})
    calls = tools_mod._tool_calls_from_acc(acc)
    assert len(calls) == 1
    assert calls[0].id == "call-1"
    assert calls[0].function.name == "calculator"
    assert calls[0].function.arguments == '{"expression":"1+1"}'


@pytest.mark.asyncio
async def test_litellm_with_tools_stream_emits_content(monkeypatch):
    class _Chunk:
        def __init__(self, content=None, tool_calls=None, usage=None):
            delta = SimpleNamespace(content=content, tool_calls=tool_calls)
            self.choices = [SimpleNamespace(delta=delta)]
            self.usage = usage

    async def fake_acompletion(**kwargs):
        assert kwargs.get("stream") is True
        assert kwargs.get("tools")

        async def gen():
            yield _Chunk(content="答")
            yield _Chunk(content="案")

        return gen()

    monkeypatch.setattr(tools_mod.litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(tools_mod, "_ensure_messages_valid_for_chat", lambda *a, **k: None)
    monkeypatch.setattr(tools_mod, "resolve_litellm_model", lambda m: "openai/gpt-test")
    monkeypatch.setattr(tools_mod, "_resolve_api_base", lambda m: None)

    deltas: list[str] = []

    async def on_delta(text: str) -> None:
        deltas.append(text)

    model = SimpleNamespace(api_key_encrypted=None, model_type="chat")
    out = await tools_mod._litellm_with_tools(
        model,
        [{"role": "user", "content": "q"}],
        [{"type": "function", "function": {"name": "calculator", "parameters": {}}}],
        temperature=0.2,
        on_delta=on_delta,
    )
    assert out.choices[0].message.content == "答案"
    assert out.choices[0].message.tool_calls is None
    assert deltas == ["答", "案"]
