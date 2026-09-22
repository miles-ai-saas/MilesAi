"""agent_executor 适配层定向单测：meta/invoke 委托与确认信号转换。

monkeypatch 均打到 ``agent_executor`` 模块命名空间（from-import 绑定），
db/ctx 用占位 object()——meta/invoke 被假实现替换，不落真实 DB。
"""

import asyncio
from uuid import uuid4

import pytest

from miles_integrations.langchain.tool_agent.tool_contract import ToolConfirmationSignal
from miles_portal.tenant.tools.confirmation import ToolConfirmationRequired
from miles_portal.tenant.tools.services import agent_executor as executor_mod
from miles_portal.tenant.tools.services.agent_executor import AgentToolExecutor


def test_meta_delegates_to_resolve_tool_meta(monkeypatch):
    calls = []

    async def fake_resolve_tool_meta(db, ctx, slug, *, tool_id=None):
        calls.append((db, ctx, slug, tool_id))
        return {"slug": slug, "require_confirmation": False, "source": "builtin"}

    monkeypatch.setattr(executor_mod, "resolve_tool_meta", fake_resolve_tool_meta)

    db, ctx = object(), object()
    executor = AgentToolExecutor(db, ctx, agent_id=None, actor_user_id=None)
    tool_id = uuid4()

    out = asyncio.run(executor.meta("calc", tool_id=tool_id))

    assert out == {"slug": "calc", "require_confirmation": False, "source": "builtin"}
    assert calls == [(db, ctx, "calc", tool_id)]


def test_invoke_delegates_params_and_confirmed(monkeypatch):
    calls = []

    async def fake_invoke_tool_with_context(
        db,
        ctx,
        name,
        params,
        *,
        tool_id=None,
        confirmed=False,
        actor_user_id=None,
        agent_id=None,
        invoke_source="api",
    ):
        calls.append(
            {
                "db": db,
                "ctx": ctx,
                "name": name,
                "params": params,
                "tool_id": tool_id,
                "confirmed": confirmed,
                "actor_user_id": actor_user_id,
                "agent_id": agent_id,
                "invoke_source": invoke_source,
            }
        )
        return {"ok": True}

    monkeypatch.setattr(executor_mod, "invoke_tool_with_context", fake_invoke_tool_with_context)

    db, ctx = object(), object()
    agent_id, actor_user_id = uuid4(), uuid4()
    executor = AgentToolExecutor(
        db,
        ctx,
        agent_id=agent_id,
        actor_user_id=actor_user_id,
        invoke_source="agent",
    )
    tool_id = uuid4()

    out = asyncio.run(executor.invoke("calc", {"a": 1}, confirmed=True, tool_id=tool_id))

    assert out == {"ok": True}
    assert calls == [
        {
            "db": db,
            "ctx": ctx,
            "name": "calc",
            "params": {"a": 1},
            "tool_id": tool_id,
            "confirmed": True,
            "actor_user_id": actor_user_id,
            "agent_id": agent_id,
            "invoke_source": "agent",
        }
    ]


def test_invoke_converts_confirmation_required_to_signal(monkeypatch):
    async def fake_invoke_tool_with_context(*args, **kwargs):
        raise ToolConfirmationRequired("calc", "计算器", None, {"a": 1})

    monkeypatch.setattr(executor_mod, "invoke_tool_with_context", fake_invoke_tool_with_context)

    executor = AgentToolExecutor(object(), object(), agent_id=None, actor_user_id=None)

    with pytest.raises(ToolConfirmationSignal) as exc_info:
        asyncio.run(executor.invoke("calc", {"a": 1}))

    exc = exc_info.value
    assert exc.slug == "calc"
    assert exc.tool_name == "计算器"
    assert exc.tool_description is None
    assert exc.params == {"a": 1}


class _RecordingShortSession:
    """假 AsyncSessionLocal：记录开合与 commit/rollback。"""

    def __init__(self) -> None:
        self.entered = 0
        self.exited = 0
        self.events: list[str] = []

    async def commit(self) -> None:
        self.events.append("commit")

    async def rollback(self) -> None:
        self.events.append("rollback")

    async def __aenter__(self) -> "_RecordingShortSession":
        self.entered += 1
        return self

    async def __aexit__(self, *exc: object) -> bool:
        self.exited += 1
        return False


def test_short_session_invoke_commits_on_success(monkeypatch):
    from miles_portal.tenant.tools.services.agent_executor import (
        ShortSessionAgentToolExecutor,
        build_short_session_agent_tool_executor,
    )

    short = _RecordingShortSession()
    monkeypatch.setattr(executor_mod, "AsyncSessionLocal", lambda: short)

    seen: list[object] = []

    async def fake_invoke(db, ctx, name, params, **kwargs):
        seen.append(db)
        return {"ok": True}

    monkeypatch.setattr(executor_mod, "invoke_tool_with_context", fake_invoke)

    ctx = object()
    executor = build_short_session_agent_tool_executor(
        ctx, agent_id=None, actor_user_id=None, invoke_source="agent"
    )
    assert isinstance(executor, ShortSessionAgentToolExecutor)

    out = asyncio.run(executor.invoke("calc", {"a": 1}))

    assert out == {"ok": True}
    assert seen == [short]
    assert (short.entered, short.exited) == (1, 1)
    assert short.events == ["commit"]


def test_short_session_invoke_commits_on_confirmation(monkeypatch):
    """确认路径须 commit，以持久化 confirmation_required 审计日志。"""
    from miles_portal.tenant.tools.services.agent_executor import ShortSessionAgentToolExecutor

    short = _RecordingShortSession()
    monkeypatch.setattr(executor_mod, "AsyncSessionLocal", lambda: short)

    async def fake_invoke(*args, **kwargs):
        raise ToolConfirmationRequired("calc", "计算器", None, {"a": 1})

    monkeypatch.setattr(executor_mod, "invoke_tool_with_context", fake_invoke)

    executor = ShortSessionAgentToolExecutor(
        object(), agent_id=None, actor_user_id=None, invoke_source="agent"
    )

    with pytest.raises(ToolConfirmationSignal) as exc_info:
        asyncio.run(executor.invoke("calc", {"a": 1}))

    assert exc_info.value.slug == "calc"
    assert short.events == ["commit"]
    assert (short.entered, short.exited) == (1, 1)


def test_short_session_invoke_rollbacks_on_exception(monkeypatch):
    from miles_portal.tenant.tools.services.agent_executor import ShortSessionAgentToolExecutor

    short = _RecordingShortSession()
    monkeypatch.setattr(executor_mod, "AsyncSessionLocal", lambda: short)

    async def fake_invoke(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(executor_mod, "invoke_tool_with_context", fake_invoke)

    executor = ShortSessionAgentToolExecutor(
        object(), agent_id=None, actor_user_id=None, invoke_source="agent"
    )

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(executor.invoke("calc", {"a": 1}))

    assert short.events == ["rollback"]
    assert (short.entered, short.exited) == (1, 1)


def test_short_session_meta_uses_own_session(monkeypatch):
    from miles_portal.tenant.tools.services.agent_executor import ShortSessionAgentToolExecutor

    short = _RecordingShortSession()
    monkeypatch.setattr(executor_mod, "AsyncSessionLocal", lambda: short)

    async def fake_resolve(db, ctx, slug, *, tool_id=None):
        assert db is short
        return {"slug": slug}

    monkeypatch.setattr(executor_mod, "resolve_tool_meta", fake_resolve)

    executor = ShortSessionAgentToolExecutor(
        object(), agent_id=None, actor_user_id=None
    )
    out = asyncio.run(executor.meta("calc"))

    assert out == {"slug": "calc"}
    assert short.events == ["commit"]
    assert (short.entered, short.exited) == (1, 1)
