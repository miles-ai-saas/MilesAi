"""LiteLLM 流式对话与 ainvoke_chat on_delta 分支测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from miles_ai.integrations.litellm.adapter import litellm_chat_completion_stream
from tests.miles_ai.integrations.litellm.test_litellm_adapter import _model


class Delta:
    def __init__(self, content):
        self.content = content


class Choice:
    def __init__(self, content):
        self.delta = Delta(content)


class Chunk:
    def __init__(self, content, usage=None):
        self.choices = [Choice(content)] if content is not None else []
        self.usage = usage


@pytest.mark.asyncio
async def test_litellm_chat_completion_stream_calls_on_delta_and_returns_full():
    chunks: list[str] = []

    async def on_delta(t: str) -> None:
        chunks.append(t)

    async def fake_stream(**kwargs):
        assert kwargs.get("stream") is True

        async def gen():
            yield Chunk("你")
            yield Chunk("好")
            yield Chunk(None, usage=MagicMock(prompt_tokens=1, completion_tokens=2, total_tokens=3))

        return gen()

    m = _model()

    with (
        patch("miles_ai.integrations.litellm.adapter._import_litellm") as imp,
        patch("miles_ai.integrations.litellm.adapter.resolve_litellm_model", return_value="openai/gpt-test"),
        patch("miles_ai.integrations.litellm.adapter._ensure_messages_valid_for_chat"),
        patch("miles_ai.integrations.litellm.adapter._resolve_api_base", return_value=None),
    ):
        litellm = MagicMock()
        litellm.acompletion = AsyncMock(side_effect=fake_stream)
        imp.return_value = litellm
        text = await litellm_chat_completion_stream(m, [{"role": "user", "content": "hi"}], on_delta=on_delta)

    assert text == "你好"
    assert chunks == ["你", "好"]


@pytest.mark.asyncio
async def test_ainvoke_chat_uses_stream_when_on_delta_set():
    from miles_ai.integrations.langchain.chat_models import ainvoke_chat

    m = _model()
    captured: dict[str, object] = {}

    async def on_delta(t: str) -> None:
        captured["delta"] = t

    with (
        patch(
            "miles_ai.integrations.langchain.chat_models.litellm_chat_completion_stream",
            new_callable=AsyncMock,
            return_value="streamed",
        ) as mock_stream,
        patch(
            "miles_ai.integrations.langchain.chat_models.litellm_chat_completion",
            new_callable=AsyncMock,
        ) as mock_non_stream,
    ):
        out = await ainvoke_chat(
            m,
            [{"role": "user", "content": "hi"}],
            on_delta=on_delta,
        )

    assert out == "streamed"
    mock_stream.assert_awaited_once()
    mock_non_stream.assert_not_awaited()
    call_kwargs = mock_stream.await_args.kwargs
    assert call_kwargs["on_delta"] is on_delta


@pytest.mark.asyncio
async def test_ainvoke_chat_uses_non_stream_when_on_delta_none():
    from miles_ai.integrations.langchain.chat_models import ainvoke_chat

    m = _model()

    with (
        patch(
            "miles_ai.integrations.langchain.chat_models.litellm_chat_completion_stream",
            new_callable=AsyncMock,
        ) as mock_stream,
        patch(
            "miles_ai.integrations.langchain.chat_models.litellm_chat_completion",
            new_callable=AsyncMock,
            return_value="non-streamed",
        ) as mock_non_stream,
    ):
        out = await ainvoke_chat(m, [{"role": "user", "content": "hi"}])

    assert out == "non-streamed"
    mock_non_stream.assert_awaited_once()
    mock_stream.assert_not_awaited()
