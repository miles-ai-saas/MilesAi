"""平台风控运行时单元测试。"""

import time
from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_core.models.risk import RateLimitScope
from miles_core.risk import enforce as enforce_mod
from miles_core.risk.enforce import PlatformRiskEnforcer


class _FakeRedis:
    """只实现 ``check_rate_limit`` 用到的两条命令的固定窗口替身。"""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, _key: str, _ttl: int) -> bool:
        return True


class _RiskDb:
    """``_ensure_cache`` 的会话替身：第一次 ``execute`` 取 IP 黑名单（空），第二次取规则。"""

    def __init__(self, rules: list[object]) -> None:
        self._batches: list[list[object]] = [[], rules]

    async def __aenter__(self) -> "_RiskDb":
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def execute(self, _stmt: object) -> object:
        rows = self._batches.pop(0) if self._batches else []
        return SimpleNamespace(scalars=lambda: iter(rows))


def _rule(*, scope: str, limit: int = 1, pattern: str = "/api/v1/open/a2a/*") -> object:
    return SimpleNamespace(id=uuid4(), path_pattern=pattern, limit_per_minute=limit, scope=scope)


def _enforcer(monkeypatch, rules: list[object], redis: _FakeRedis) -> PlatformRiskEnforcer:  # noqa: ANN001
    monkeypatch.setattr(enforce_mod, "AsyncSessionLocal", lambda: _RiskDb(rules))
    monkeypatch.setattr(enforce_mod, "get_redis", lambda: redis)
    return PlatformRiskEnforcer()


def _freeze_time(monkeypatch, now: float) -> None:  # noqa: ANN001
    """冻结 ``enforce`` 用到的时钟。

    整体换成只带 ``time`` 的 ``SimpleNamespace`` 会砸掉 ``_ensure_cache`` 的
    ``time.monotonic()``（AttributeError），故补齐实际用到的两个成员，且只替换
    ``enforce`` 模块持有的 ``time`` 名字、不动全局 ``time`` 模块。
    """
    monkeypatch.setattr(enforce_mod, "time", SimpleNamespace(time=lambda: now, monotonic=time.monotonic))


def test_match_path_wildcard():
    enforcer = PlatformRiskEnforcer()
    assert enforcer._match_path("/api/v1/*", "/api/v1/auth/login") is True
    assert enforcer._match_path("/api/v1/*", "/api/admin/v1/tenants") is False


@pytest.mark.asyncio
async def test_scope_filters_rules_by_dimension(monkeypatch):  # noqa: ANN001
    """一条 ip 规则不参与 api_key 维度的计数：两个维度各自独立分桶。"""
    rule = _rule(scope="ip", limit=1)
    enforcer = _enforcer(monkeypatch, [rule], _FakeRedis())

    for _ in range(3):
        assert await enforcer.check_rate_limit("/api/v1/open/a2a/agents/x", "key:k1", scope=RateLimitScope.API_KEY) is None


@pytest.mark.asyncio
async def test_api_key_scope_returns_hit_with_retry_after(monkeypatch):  # noqa: ANN001
    """超限时回命中信息，供调用方写 429 + ``Retry-After``。"""
    rule = _rule(scope="api_key", limit=2)
    enforcer = _enforcer(monkeypatch, [rule], _FakeRedis())

    assert await enforcer.check_rate_limit("/api/v1/open/a2a/agents/x", "key:k1", scope=RateLimitScope.API_KEY) is None
    assert await enforcer.check_rate_limit("/api/v1/open/a2a/agents/x", "key:k1", scope=RateLimitScope.API_KEY) is None
    hit = await enforcer.check_rate_limit("/api/v1/open/a2a/agents/x", "key:k1", scope=RateLimitScope.API_KEY)

    assert hit is not None
    assert hit.rule_id == rule.id
    assert hit.limit_per_minute == 2
    # 固定窗口剩余秒数：至少 1 —— 回 0 等于让对端立刻重试，比不回更糟
    assert 1 <= hit.retry_after_seconds <= 60


@pytest.mark.parametrize(
    ("now", "expected_retry_after"),
    [
        # 窗口首刻：整个窗口都还没走，剩余即整窗 60 秒
        (60.0, 60),
        # 窗口中段：ceil(120 - 100.5) = 20
        (100.5, 20),
        # 窗口末刻：不足 1 秒也回 1 —— 回 0 等于让对端立刻重试，比不回更糟
        (119.999, 1),
    ],
)
@pytest.mark.asyncio
async def test_retry_after_seconds_follows_window_boundary(monkeypatch, now, expected_retry_after):  # noqa: ANN001
    """``retry_after_seconds`` 必须是「距窗口结束的剩余秒数」，而不是某个常量。

    区间断言（``1 <= x <= 60``）区分不了真实计算与 ``x=30`` 之类的硬编码，故这里冻结
    时钟取窗口首刻 / 中段 / 末刻三个精确值：任何不随窗口边界变化的取值都会失败。
    """
    _freeze_time(monkeypatch, now)
    rule = _rule(scope="api_key", limit=1)
    enforcer = _enforcer(monkeypatch, [rule], _FakeRedis())

    path = "/api/v1/open/a2a/agents/x"
    assert await enforcer.check_rate_limit(path, "key:k1", scope=RateLimitScope.API_KEY) is None
    hit = await enforcer.check_rate_limit(path, "key:k1", scope=RateLimitScope.API_KEY)

    assert hit is not None
    assert hit.retry_after_seconds == expected_retry_after


@pytest.mark.asyncio
async def test_buckets_are_per_client_key(monkeypatch):  # noqa: ANN001
    """一把 Key 超限不得连坐到另一把：轮换 Key / 多对端接入要靠这条成立。"""
    rule = _rule(scope="api_key", limit=1)
    enforcer = _enforcer(monkeypatch, [rule], _FakeRedis())

    assert await enforcer.check_rate_limit("/api/v1/open/a2a/agents/x", "key:k1", scope=RateLimitScope.API_KEY) is None
    assert await enforcer.check_rate_limit("/api/v1/open/a2a/agents/x", "key:k2", scope=RateLimitScope.API_KEY) is None
    assert await enforcer.check_rate_limit("/api/v1/open/a2a/agents/x", "key:k1", scope=RateLimitScope.API_KEY) is not None


def test_scope_column_defaults_to_ip_for_backward_compatibility():
    """存量规则的语义不能变：新列默认 ``ip``，加了列之后它们仍按来源 IP 生效。"""
    from sqlalchemy import String

    from miles_core.models.risk import RateLimitRule

    column = RateLimitRule.__table__.c["scope"]
    assert isinstance(column.type, String)
    assert column.type.length == 16
    assert column.nullable is False
    assert column.default is not None and column.default.arg == "ip"
    assert column.server_default is not None
