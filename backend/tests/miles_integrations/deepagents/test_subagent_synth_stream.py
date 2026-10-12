"""平台规划子智能体：最终综合回答透传 on_delta。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from miles_core.models.agent import Agent, AgentSubAgentBinding
from miles_integrations.deepagents.io import ParentChatInput
from miles_integrations.deepagents import orchestrator as orch


class _Svc:
    async def chat_as_child_simple(self, child_id, *, query, inputs=None, conversation_id=None):  # noqa: ANN001
        return SimpleNamespace(answer=f"子答:{query}")

    async def resolve_system_prompt(self, agent):  # noqa: ANN001
        return "你是主协调者"

    async def resolve_invoke_model(self, model):  # noqa: ANN001
        return model

    def chat_usage_sink(self, model, *, source_id=None):  # noqa: ANN001
        return None


@pytest.mark.asyncio
async def test_platform_synth_forwards_on_delta(monkeypatch):
    child_id = uuid4()
    parent = Agent(
        id=uuid4(),
        tenant_id=uuid4(),
        name="parent",
        config={"force_platform_planner": True, "planner": "platform"},
        model_config=SimpleNamespace(id=uuid4()),
    )
    binding = AgentSubAgentBinding(
        parent_agent_id=parent.id,
        child_agent_id=child_id,
        role_hint="worker",
        sort_order=0,
    )
    binding.child_agent = SimpleNamespace(id=child_id, name="子工位", description="d")

    async def fake_plan(*args, **kwargs):  # noqa: ANN001
        return [{"sub_agent_id": str(child_id), "task": "做一件事"}]

    deltas: list[str] = []

    async def fake_ainvoke(model, messages, *, temperature=0.7, usage_sink=None, on_delta=None):  # noqa: ANN001
        assert on_delta is not None
        await on_delta("综")
        await on_delta("合")
        return "综合答案"

    monkeypatch.setattr(orch, "_platform_plan", fake_plan)
    monkeypatch.setattr(orch, "ainvoke_chat", fake_ainvoke)
    monkeypatch.setattr(orch, "_should_use_deepagents", lambda _p: False)

    async def on_delta(text: str) -> None:
        deltas.append(text)

    result = await orch.run_subagent_planned_chat(
        _Svc(),
        parent,
        [binding],
        ParentChatInput(query="用户问"),
        on_delta=on_delta,
    )
    assert result.answer == "综合答案"
    assert deltas == ["综", "合"]
    assert any(s.get("type") == "subagent" for s in result.steps)


@pytest.mark.asyncio
async def test_platform_plan_llm_does_not_receive_on_delta(monkeypatch):
    """规划轮 ainvoke_chat 不应带 on_delta。"""
    child_id = uuid4()
    parent = Agent(
        id=uuid4(),
        tenant_id=uuid4(),
        name="parent",
        config={"force_platform_planner": True},
        model_config=SimpleNamespace(id=uuid4()),
    )
    binding = AgentSubAgentBinding(
        parent_agent_id=parent.id,
        child_agent_id=child_id,
        role_hint=None,
        sort_order=0,
    )
    binding.child_agent = SimpleNamespace(id=child_id, name="子", description="")

    calls: list[dict] = []

    async def fake_ainvoke(model, messages, *, temperature=0.7, usage_sink=None, on_delta=None):  # noqa: ANN001
        calls.append({"on_delta": on_delta, "content": messages[0]["content"][:20]})
        if "任务规划器" in messages[0]["content"]:
            return '{"steps":[{"sub_agent_id":"%s","task":"t"}]}' % child_id
        if on_delta:
            await on_delta("终")
        return "最终"

    monkeypatch.setattr(orch, "ainvoke_chat", fake_ainvoke)
    monkeypatch.setattr(orch, "_should_use_deepagents", lambda _p: False)

    await orch.run_subagent_planned_chat(
        _Svc(),
        parent,
        [binding],
        ParentChatInput(query="q"),
        on_delta=AsyncMock(),
    )
    assert calls[0]["on_delta"] is None  # 规划
    assert calls[1]["on_delta"] is not None  # 综合
