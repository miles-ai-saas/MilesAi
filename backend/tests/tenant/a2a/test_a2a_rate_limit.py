"""A2A 按 API Key 限流：维度取值、命中留痕与失败姿态。

服务层单测，不连库不连 Redis —— 风控单例的两条方法在这里被替换。
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from miles_core.risk import enforce as enforce_mod
from miles_core.risk.enforce import RateLimitHit
from miles_core.tenant import TenantContext
from miles_portal.tenant.a2a.services import limits as limits_mod

AGENT_ID = uuid4()
PATH = f"/api/v1/open/a2a/agents/{AGENT_ID}"


def _ctx(*, with_key: bool = True) -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="a2a-peer",
        is_superuser=False,
        permissions=frozenset({"agent:read"}),
        auth_via="api_key",
        api_key_id=uuid4() if with_key else None,
    )


def test_tenant_context_without_api_key_id_is_still_constructible():
    """既有构造点（JWT 通道）不传该字段也必须能构造 —— 默认 ``None`` 是兼容的关键。"""
    ctx = TenantContext(user_id=uuid4(), tenant_id=uuid4(), username="u", is_superuser=False, permissions=frozenset())
    assert ctx.api_key_id is None


@pytest.mark.asyncio
async def test_hit_is_scoped_by_key_id_and_recorded(monkeypatch):  # noqa: ANN001
    """命中判定按「Key 行 id」分桶，并留一条风控事件。"""
    seen: dict = {}
    events: list[dict] = []
    hit = RateLimitHit(rule_id=uuid4(), limit_per_minute=30, retry_after_seconds=12)
    ctx = _ctx()
    assert ctx.api_key_id is not None

    async def fake_check(path, client_key, *, scope):  # noqa: ANN001
        seen["path"] = path
        seen["client_key"] = client_key
        seen["scope"] = scope
        return hit

    async def fake_record(**kwargs):  # noqa: ANN003
        events.append(kwargs)

    monkeypatch.setattr(enforce_mod.platform_risk_enforcer, "check_rate_limit", fake_check)
    monkeypatch.setattr(enforce_mod.platform_risk_enforcer, "record_event", fake_record)

    got = await limits_mod.check_a2a_rate_limit(ctx, AGENT_ID, path=PATH, ip="1.2.3.4")

    assert got is hit
    assert seen["path"] == PATH
    assert seen["scope"].value == "api_key"
    # 桶键只带 Key 的行 id：Redis 键不该承载凭证材料（明文或哈希都不行）
    assert seen["client_key"] == f"key:{ctx.api_key_id}"
    assert len(events) == 1
    assert events[0]["event_type"] == "a2a_rate_limit"
    assert events[0]["tenant_id"] == ctx.tenant_id
    assert events[0]["ip_address"] == "1.2.3.4"
    assert events[0]["detail"]["apiKeyId"] == str(ctx.api_key_id)


@pytest.mark.asyncio
async def test_no_hit_records_nothing(monkeypatch):  # noqa: ANN001
    events: list[dict] = []

    async def fake_check(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return None

    async def fake_record(**kwargs):  # noqa: ANN003
        events.append(kwargs)

    monkeypatch.setattr(enforce_mod.platform_risk_enforcer, "check_rate_limit", fake_check)
    monkeypatch.setattr(enforce_mod.platform_risk_enforcer, "record_event", fake_record)

    assert await limits_mod.check_a2a_rate_limit(_ctx(), AGENT_ID, path=PATH, ip=None) is None
    assert events == []


@pytest.mark.asyncio
async def test_fails_open_when_redis_path_raises(monkeypatch):  # noqa: ANN001
    """Redis 抖动不得让对外端点整体不可用：限流是保护措施，不是正确性依赖。"""

    async def boom(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("redis down")

    monkeypatch.setattr(enforce_mod.platform_risk_enforcer, "check_rate_limit", boom)

    assert await limits_mod.check_a2a_rate_limit(_ctx(), AGENT_ID, path=PATH, ip=None) is None


@pytest.mark.asyncio
async def test_hit_is_still_enforced_when_event_write_fails(monkeypatch):  # noqa: ANN001
    """风控事件写失败不能反向变成放行 —— 命中判定已经成立，放行才是错的方向。"""
    hit = RateLimitHit(rule_id=uuid4(), limit_per_minute=1, retry_after_seconds=5)

    async def fake_check(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return hit

    async def boom(**_kwargs):  # noqa: ANN003
        raise RuntimeError("db down")

    monkeypatch.setattr(enforce_mod.platform_risk_enforcer, "check_rate_limit", fake_check)
    monkeypatch.setattr(enforce_mod.platform_risk_enforcer, "record_event", boom)

    assert await limits_mod.check_a2a_rate_limit(_ctx(), AGENT_ID, path=PATH, ip=None) is hit


@pytest.mark.asyncio
async def test_skips_without_api_key_identity(monkeypatch):  # noqa: ANN001
    """无 Key 身份时不查 Redis（返回 None），且不写事件 —— 不得凭空编造桶键。"""
    called = {"check": 0}

    async def fake_check(*_args, **_kwargs):  # noqa: ANN002, ANN003
        called["check"] += 1
        return None

    monkeypatch.setattr(enforce_mod.platform_risk_enforcer, "check_rate_limit", fake_check)

    assert await limits_mod.check_a2a_rate_limit(_ctx(with_key=False), AGENT_ID, path=PATH, ip=None) is None
    assert called["check"] == 0
