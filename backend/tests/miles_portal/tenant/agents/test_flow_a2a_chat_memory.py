"""Flow / A2A 宿主短程记忆注入：system 后缀与 steps。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from miles_portal.tenant.a2a.invoke import run_a2a_host_chat
from miles_portal.tenant.agents.schemas.agent import ChatRequest


@pytest.mark.asyncio
async def test_a2a_host_appends_history_to_system_prompt():
    agent_id = uuid4()
    agent = MagicMock()
    agent.id = agent_id
    agent.model_config_id = uuid4()
    agent.model_config = MagicMock()
    agent.config = {"temperature": 0.2}

    binding = MagicMock()
    binding.enabled = True
    binding.peer = MagicMock()

    svc = MagicMock()
    svc.db = AsyncMock()
    svc.ctx.tenant_id = uuid4()
    svc.resolve_system_prompt = AsyncMock(return_value="宿主提示")
    svc.resolve_invoke_model = AsyncMock(return_value=MagicMock())
    svc.chat_usage_sink = MagicMock(return_value=None)
    svc.db.commit = AsyncMock()

    history = [{"role": "user", "content": "上次问题"}, {"role": "assistant", "content": "上次回答"}]
    body = ChatRequest(query="新问题", conversation_id="sess-1")

    with (
        patch(
            "miles_portal.tenant.a2a.invoke.list_host_peer_bindings",
            new_callable=AsyncMock,
            return_value=[binding],
        ),
        patch(
            "miles_portal.tenant.a2a.invoke.resolve_a2a_plan_items",
            new_callable=AsyncMock,
            return_value=([], []),
        ),
        patch(
            "miles_portal.tenant.a2a.invoke.load_chat_history_messages",
            new_callable=AsyncMock,
            return_value=history,
        ),
        patch(
            "miles_portal.tenant.a2a.invoke.ainvoke_chat",
            new_callable=AsyncMock,
            return_value="最终答",
        ) as mocked_llm,
    ):
        resp = await run_a2a_host_chat(svc, agent, body)

    assert any(s.get("type") == "chat_memory" and s.get("route") == "a2a_host" for s in resp.steps)
    prompt = mocked_llm.await_args.args[1][0]["content"]
    assert "【近期对话】" in prompt
    assert "上次问题" in prompt
    assert "新问题" in prompt


@pytest.mark.asyncio
async def test_flow_path_sets_system_prompt_history_suffix():
    """``_run_published_flow`` 在 RunContext.system_prompt 追加近期对话块。"""
    from miles_portal.tenant.agents.services.agent.chat_entry import AgentChatEntryMixin

    mixin = AgentChatEntryMixin()
    mixin.db = AsyncMock()
    mixin.ctx = SimpleNamespace(tenant_id=uuid4())
    mixin.flow_repo = MagicMock()
    flow_id = uuid4()
    agent_id = uuid4()
    agent = MagicMock()
    agent.published_flow_id = flow_id

    flow = MagicMock()
    flow.id = flow_id
    flow.current_version = 1
    version = MagicMock()
    version.graph_json = {"nodes": [], "edges": []}
    mixin.flow_repo.get_by_id = AsyncMock(return_value=flow)
    mixin.flow_repo.get_version = AsyncMock(return_value=version)

    ctx = SimpleNamespace(system_prompt="流程系统提示")
    mixin.flow_run_context = AsyncMock(return_value=ctx)
    mixin.db.commit = AsyncMock()

    history = [{"role": "user", "content": "历史问"}]
    runtime = MagicMock()
    runtime.run = AsyncMock(return_value=SimpleNamespace(output="流程输出", steps=[{"type": "llm"}]))

    body = ChatRequest(query="本轮问", conversation_id="c1")
    with (
        patch(
            "miles_portal.tenant.agents.services.agent.chat_entry.load_chat_history_messages",
            new_callable=AsyncMock,
            return_value=history,
        ),
        patch(
            "miles_portal.tenant.agents.services.agent.chat_entry.get_flow_runtime",
            return_value=runtime,
        ),
    ):
        resp = await mixin._run_published_flow(agent, agent_id, body, query="本轮问", kb_ids=[])

    assert "【近期对话】" in (ctx.system_prompt or "")
    assert "历史问" in (ctx.system_prompt or "")
    assert any(s.get("type") == "chat_memory" and s.get("route") == "flow" for s in resp.steps)
    assert resp.answer == "流程输出"
