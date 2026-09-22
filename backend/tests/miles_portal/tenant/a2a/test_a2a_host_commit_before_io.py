"""A2A host：Peer HTTP / 编排 LLM 前须 commit 释放请求会话。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from miles_portal.tenant.a2a import invoke as invoke_mod
from miles_portal.tenant.agents.schemas.agent import ChatRequest


class _TxnDb:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def commit(self) -> None:
        self.events.append("commit")


def _run(coro):
    return asyncio.run(coro)


def _svc(db: _TxnDb) -> SimpleNamespace:
    async def resolve_system_prompt(agent):  # noqa: ANN001, ARG001
        return "sys"

    async def resolve_invoke_model(cfg):  # noqa: ANN001, ARG001
        return MagicMock()

    return SimpleNamespace(
        db=db,
        ctx=SimpleNamespace(tenant_id=uuid4()),
        resolve_system_prompt=resolve_system_prompt,
        resolve_invoke_model=resolve_invoke_model,
        chat_usage_sink=lambda model, source_id=None: MagicMock(),
    )


def _agent() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        model_config_id=uuid4(),
        model_config=MagicMock(),
        config={"temperature": 0.7},
    )


def _binding() -> SimpleNamespace:
    peer_id = uuid4()
    return SimpleNamespace(
        peer_id=peer_id,
        enabled=True,
        peer=SimpleNamespace(id=peer_id, name="peer", card_display_name="Peer"),
        role_hint=None,
        trigger_keywords=[],
    )


def test_host_no_plan_commits_before_llm(monkeypatch):
    db = _TxnDb()
    svc = _svc(db)
    agent = _agent()
    binding = _binding()

    monkeypatch.setattr(invoke_mod, "list_host_peer_bindings", AsyncMock(return_value=[binding]))
    monkeypatch.setattr(
        invoke_mod,
        "resolve_a2a_plan_items",
        AsyncMock(return_value=([], [])),
    )

    async def fake_ainvoke(*_a, **_k):
        db.events.append("llm")
        return "答"

    monkeypatch.setattr(invoke_mod, "ainvoke_chat", AsyncMock(side_effect=fake_ainvoke))

    out = _run(invoke_mod.run_a2a_host_chat(svc, agent, ChatRequest(query="q")))

    assert out.answer == "答"
    assert db.events == ["commit", "llm"]


def test_host_with_plan_commits_before_peer_http(monkeypatch):
    db = _TxnDb()
    svc = _svc(db)
    agent = _agent()
    binding = _binding()
    plan = [{"peer_id": str(binding.peer_id), "task": "t"}]

    monkeypatch.setattr(invoke_mod, "list_host_peer_bindings", AsyncMock(return_value=[binding]))
    monkeypatch.setattr(
        invoke_mod,
        "resolve_a2a_plan_items",
        AsyncMock(return_value=(plan, [{"type": "a2a_plan", "steps": plan}])),
    )

    async def fake_execute(*_a, **_k):
        db.events.append("peer_http")
        return ["【外部】ok"]

    async def fake_ainvoke(*_a, **_k):
        db.events.append("llm")
        return "综合答"

    monkeypatch.setattr(invoke_mod, "execute_a2a_calls", AsyncMock(side_effect=fake_execute))
    monkeypatch.setattr(invoke_mod, "ainvoke_chat", AsyncMock(side_effect=fake_ainvoke))

    out = _run(invoke_mod.run_a2a_host_chat(svc, agent, ChatRequest(query="q")))

    assert out.answer == "综合答"
    assert db.events[0] == "commit"
    assert "peer_http" in db.events
    assert db.events.index("commit") < db.events.index("peer_http")
    assert db.events.index("commit") < db.events.index("llm")
