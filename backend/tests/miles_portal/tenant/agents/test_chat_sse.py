"""HTTP 对话 SSE：帧格式与 delta/done/error 编排。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_core.models.agent.chat_io import ChatResponse, PendingToolCall
from miles_portal.tenant.agents.schemas.agent import ChatRequest
from miles_portal.tenant.agents.services import chat_sse as mod


def test_format_sse_has_event_and_data():
    frame = mod.format_sse("chat.delta", {"text": "你"})
    assert frame.startswith("event: chat.delta\n")
    assert 'data: {"text": "你"}' in frame or 'data: {"text":"你"}' in frame
    assert frame.endswith("\n\n")


@pytest.mark.asyncio
async def test_iter_emits_delta_then_done(monkeypatch):
    agent_id = uuid4()
    body = ChatRequest(query="hi")

    class _FakeSvc:
        def __init__(self, db, ctx):
            pass

        async def chat(self, _aid, _body, *, on_delta=None):
            assert on_delta is not None
            await on_delta("你")
            await on_delta("好")
            return ChatResponse(answer="你好", steps=[{"type": "direct"}])

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    monkeypatch.setattr(mod, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(mod, "AgentService", _FakeSvc)

    frames = [frame async for frame in mod.iter_agent_chat_sse(SimpleNamespace(), agent_id, body)]
    assert any("event: chat.delta" in f and "你" in f for f in frames)
    assert any("event: chat.delta" in f and "好" in f for f in frames)
    assert any("event: chat.done" in f and "你好" in f for f in frames)
    assert session.commit.await_count == 1


@pytest.mark.asyncio
async def test_iter_chunks_when_no_delta(monkeypatch):
    class _FakeSvc:
        def __init__(self, db, ctx):
            pass

        async def chat(self, _aid, _body, *, on_delta=None):
            return ChatResponse(answer="abcdefghij", steps=[])

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    monkeypatch.setattr(mod, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(mod, "AgentService", _FakeSvc)

    frames = [frame async for frame in mod.iter_agent_chat_sse(SimpleNamespace(), uuid4(), ChatRequest(query="q"))]
    delta_frames = [f for f in frames if "event: chat.delta" in f]
    assert len(delta_frames) >= 1
    assert any("event: chat.done" in f for f in frames)


@pytest.mark.asyncio
async def test_iter_emits_error_on_app_error(monkeypatch):
    class _FakeSvc:
        def __init__(self, db, ctx):
            pass

        async def chat(self, _aid, _body, *, on_delta=None):
            raise BadRequestError("已禁用")

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    monkeypatch.setattr(mod, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(mod, "AgentService", _FakeSvc)

    frames = [frame async for frame in mod.iter_agent_chat_sse(SimpleNamespace(), uuid4(), ChatRequest(query="q"))]
    assert any("event: chat.error" in f and "已禁用" in f for f in frames)
    assert not any("event: chat.done" in f for f in frames)
    session.rollback.assert_awaited()


@pytest.mark.asyncio
async def test_iter_emits_tool_confirm(monkeypatch):
    class _FakeSvc:
        def __init__(self, db, ctx):
            pass

        async def chat(self, _aid, _body, *, on_delta=None):
            return ChatResponse(
                answer="请确认",
                pending_tool=PendingToolCall(slug="code_execution", name="代码执行", description=None, params={"code": "1"}),
            )

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    monkeypatch.setattr(mod, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(mod, "AgentService", _FakeSvc)

    frames = [frame async for frame in mod.iter_agent_chat_sse(SimpleNamespace(), uuid4(), ChatRequest(query="q"))]
    assert any("event: tool.confirm_required" in f and "code_execution" in f for f in frames)
