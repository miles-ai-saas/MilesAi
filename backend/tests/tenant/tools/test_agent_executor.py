"""agent_executor 适配层定向单测：meta/invoke 委托与确认信号转换。

monkeypatch 均打到 ``agent_executor`` 模块命名空间（from-import 绑定），
db/ctx 用占位 object()——meta/invoke 被假实现替换，不落真实 DB。
"""

import asyncio
from uuid import uuid4

import pytest

from app.integrations.langchain.tool_agent.tool_contract import ToolConfirmationSignal
from app.tenant.tools.confirmation import ToolConfirmationRequired
from app.tenant.tools.services import agent_executor as executor_mod
from app.tenant.tools.services.agent_executor import AgentToolExecutor


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
