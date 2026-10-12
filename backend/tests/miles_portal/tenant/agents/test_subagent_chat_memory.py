"""Subagent 短程记忆：平台规划路径注入 history_block，并向下传递 conversation_id。"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from miles_integrations.deepagents.io import ParentChatInput
from miles_integrations.deepagents.orchestrator import _run_platform_planned
from miles_portal.tenant.agents.schemas.agent import ChatResponse


@pytest.mark.asyncio
async def test_platform_plan_injects_history_and_passes_conversation_id():
    parent_id = uuid4()
    child_id = uuid4()
    parent = MagicMock()
    parent.id = parent_id
    parent.model_config = MagicMock()
    parent.config = {"temperature": 0.2, "force_platform_planner": True}

    child = MagicMock()
    child.id = child_id
    child.name = "检索工位"
    child.description = "检索"
    binding = MagicMock()
    binding.child_agent_id = child_id
    binding.child_agent = child
    binding.role_hint = "retrieval"

    captured: dict = {}

    async def fake_child(cid, *, query, inputs=None, conversation_id=None):
        captured["child_id"] = cid
        captured["query"] = query
        captured["conversation_id"] = conversation_id
        captured["inputs"] = inputs
        return ChatResponse(answer="子答")

    svc = MagicMock()
    svc.resolve_system_prompt = AsyncMock(return_value="父提示")
    svc.resolve_invoke_model = AsyncMock(return_value=MagicMock())
    svc.chat_usage_sink = MagicMock(return_value=None)
    svc.chat_as_child_simple = AsyncMock(side_effect=fake_child)

    body = ParentChatInput(
        query="本轮问",
        inputs={"k": 1},
        conversation_id="sess-1",
        history_block="\n\n【近期对话】\n用户：历史问\n助手：历史答",
        history_message_count=2,
    )

    llm_calls: list[str] = []

    async def fake_ainvoke(_model, messages, **_kwargs):
        content = messages[0]["content"]
        llm_calls.append(content)
        if "任务规划器" in content:
            return f'{{"steps":[{{"sub_agent_id":"{child_id}","task":"去检索"}}]}}'
        return "综合答"

    with patch(
        "miles_integrations.deepagents.orchestrator.ainvoke_chat",
        new_callable=AsyncMock,
        side_effect=fake_ainvoke,
    ):
        result = await _run_platform_planned(svc, parent, [binding], body)

    assert result.answer == "综合答"
    assert any(s.get("type") == "chat_memory" and s.get("route") == "subagent" for s in result.steps)
    assert captured["conversation_id"] == "sess-1"
    assert captured["child_id"] == child_id
    assert "【近期对话】" in llm_calls[0]
    assert "历史问" in llm_calls[0]
    assert "【近期对话】" in llm_calls[1]
    assert "本轮问" in llm_calls[1]

