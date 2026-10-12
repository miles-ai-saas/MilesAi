"""A2A 意图路由配置与 resolve 分支测试。"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from miles_portal.tenant.a2a.intent_router import intent_router_enabled
from miles_portal.tenant.a2a.invoke import _parse_a2a_plan, resolve_a2a_plan_items
from miles_portal.tenant.a2a.models import A2aInvokePolicy, A2aPlanTrigger


class _Peer:
    def __init__(self, peer_id):
        self.id = peer_id
        self.name = "ext"
        self.card_display_name = "Ext"


class _Ref:
    def __init__(self, peer_id, keywords=None, enabled=True, role_hint=None):
        self.peer_id = peer_id
        self.enabled = enabled
        self.trigger_keywords = keywords or []
        self.role_hint = role_hint
        self.peer = _Peer(peer_id)


def _agent(*, policy: str, intent_enabled: bool = False):
    cfg: dict = {"a2a_invoke_policy": policy, "max_a2a_calls_per_turn": 2}
    if intent_enabled:
        cfg["a2a_intent_router"] = {"enabled": True}
    agent = MagicMock()
    agent.config = cfg
    agent.model_config = MagicMock()
    agent.id = uuid4()
    return agent


def test_intent_router_enabled():
    a = _agent(policy="rules_then_plan", intent_enabled=True)
    assert intent_router_enabled(a) is True
    b = _agent(policy="rules_then_plan", intent_enabled=False)
    assert intent_router_enabled(b) is False
    c = MagicMock()
    c.config = {}
    assert intent_router_enabled(c) is False


def test_parse_a2a_plan_accepts_a2a_steps():
    raw = '{"a2a_steps":[{"peer_id":"p1","task":"查订单"}]}'
    assert _parse_a2a_plan(raw) == [{"peer_id": "p1", "task": "查订单"}]


@pytest.mark.asyncio
async def test_resolve_uses_intent_router_when_enabled():
    peer_id = str(uuid4())
    agent = _agent(policy=A2aInvokePolicy.RULES_THEN_PLAN.value, intent_enabled=True)
    refs = [_Ref(peer_id, keywords=[])]

    with patch(
        "miles_portal.tenant.a2a.invoke.route_a2a_peers_by_intent",
        new_callable=AsyncMock,
        return_value=(
            [{"peer_id": peer_id, "task": "帮我查一下"}],
            {"engine": "intent_llm", "selected_peer_ids": [peer_id], "latency_ms": 12},
        ),
    ) as mocked:
        items, steps = await resolve_a2a_plan_items(agent, refs, "查一下订单", db=None, tenant_id=uuid4())

    mocked.assert_awaited_once()
    assert len(items) == 1
    assert items[0]["trigger"] == A2aPlanTrigger.INTENT.value
    assert any(s.get("type") == "a2a_intent_router" for s in steps)


@pytest.mark.asyncio
async def test_resolve_uses_plan_when_intent_disabled():
    peer_id = str(uuid4())
    agent = _agent(policy=A2aInvokePolicy.RULES_THEN_PLAN.value, intent_enabled=False)
    refs = [_Ref(peer_id, keywords=[])]

    with patch(
        "miles_portal.tenant.a2a.invoke.plan_a2a_peers",
        new_callable=AsyncMock,
        return_value=[{"peer_id": peer_id, "task": "task"}],
    ) as mocked:
        items, steps = await resolve_a2a_plan_items(agent, refs, "普通问题", db=None, tenant_id=uuid4())

    mocked.assert_awaited_once()
    assert items[0]["trigger"] == A2aPlanTrigger.PLAN.value
    assert any(s.get("type") == "a2a_plan" for s in steps)


@pytest.mark.asyncio
async def test_rules_only_skips_intent_router():
    peer_id = str(uuid4())
    agent = _agent(policy=A2aInvokePolicy.RULES_ONLY.value, intent_enabled=True)
    refs = [_Ref(peer_id, keywords=["订单"])]

    with patch(
        "miles_portal.tenant.a2a.invoke.route_a2a_peers_by_intent",
        new_callable=AsyncMock,
    ) as mocked:
        items, steps = await resolve_a2a_plan_items(agent, refs, "查订单", db=None, tenant_id=uuid4())

    mocked.assert_not_awaited()
    assert len(items) == 1
    assert items[0]["trigger"] == A2aPlanTrigger.RULE.value
