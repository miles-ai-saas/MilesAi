"""DeepAgents 库路径：astream 透传 on_delta。"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from miles_core.models.agent import Agent, AgentSubAgentBinding
from miles_integrations.deepagents.io import ParentChatInput
from miles_integrations.deepagents import runner as runner_mod


class _Svc:
    async def chat_as_child_simple(self, *a, **k):  # noqa: ANN001
        return SimpleNamespace(answer="child")

    async def resolve_system_prompt(self, agent):  # noqa: ANN001
        return "sys"

    async def resolve_invoke_model(self, model):  # noqa: ANN001
        return model

    def chat_usage_sink(self, model, *, source_id=None):  # noqa: ANN001
        return None


@pytest.mark.asyncio
async def test_run_deepagents_astream_forwards_content(monkeypatch):
    parent = Agent(
        id=uuid4(),
        tenant_id=uuid4(),
        name="p",
        config={"planner": "deepagents"},
        model_config=SimpleNamespace(id=uuid4()),
    )
    child_id = uuid4()
    binding = AgentSubAgentBinding(
        parent_agent_id=parent.id,
        child_agent_id=child_id,
        role_hint="w",
        sort_order=0,
    )
    binding.child_agent = SimpleNamespace(id=child_id, name="子", description="")

    deltas: list[str] = []

    class _FakeAgent:
        async def astream(self, state, config=None, stream_mode=None):  # noqa: ANN001
            yield ("messages", (AIMessageChunk(content="最"), {}))
            yield ("messages", (AIMessageChunk(content="终"), {}))
            # tool_call 片应跳过
            yield (
                "messages",
                (AIMessageChunk(content="", tool_call_chunks=[{"name": "task"}]), {}),
            )
            yield (
                "values",
                {
                    "messages": [
                        HumanMessage(content="q"),
                        AIMessage(content="最终"),
                    ]
                },
            )

        async def ainvoke(self, *a, **k):  # noqa: ANN001
            raise AssertionError("on_delta 路径不应走 ainvoke")

    monkeypatch.setattr(runner_mod, "create_deep_agent", lambda **kwargs: _FakeAgent())
    monkeypatch.setattr(runner_mod, "build_compiled_subagents", lambda *a, **k: [{"name": "w", "description": "d"}])
    monkeypatch.setattr(runner_mod, "get_chat_model", lambda *a, **k: object())
    monkeypatch.setattr(runner_mod, "get_checkpointer", lambda: None)

    async def on_delta(text: str) -> None:
        deltas.append(text)

    result = await runner_mod.run_deepagents_chat(
        _Svc(),
        parent,
        [binding],
        ParentChatInput(query="用户问"),
        on_delta=on_delta,
    )
    assert result.answer == "最终"
    assert deltas == ["最", "终"]


@pytest.mark.asyncio
async def test_platform_chat_model_astream(monkeypatch):
    from unittest.mock import MagicMock

    from miles_core.models.model import ModelConfig
    from miles_integrations.langchain import chat_models as cm

    class _Chunk:
        def __init__(self, text: str):
            self.choices = [SimpleNamespace(delta=SimpleNamespace(content=text, tool_calls=None))]

    async def fake_acompletion(**kwargs):
        assert kwargs.get("stream") is True

        async def gen():
            yield _Chunk("A")
            yield _Chunk("B")

        return gen()

    import litellm as litellm_mod

    monkeypatch.setattr(litellm_mod, "acompletion", fake_acompletion)
    monkeypatch.setattr(cm, "_ensure_messages_valid_for_chat", lambda *a, **k: None)
    monkeypatch.setattr(cm, "resolve_litellm_model", lambda m: "openai/gpt-test")
    monkeypatch.setattr(cm, "_resolve_api_base", lambda m: None)

    row = MagicMock(spec=ModelConfig)
    row.provider = "openai"
    row.api_key_encrypted = None
    model = cm.PlatformChatModel(model_row=row, temperature=0.1)
    parts: list[str] = []
    async for gen in model._astream([HumanMessage(content="hi")]):
        parts.append(gen.message.content)
    assert parts == ["A", "B"]
