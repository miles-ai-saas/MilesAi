"""内置 redis_kv：租户隔离与操作护栏。"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_common.redis_keys import RedisKeys
from miles_core.tenant import TenantContext
from miles_portal.tenant.tools.services import redis_kv as mod


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def ttl(self, key: str) -> int:
        if key not in self.store:
            return -2
        return self.ttls.get(key, -1)

    async def exists(self, key: str) -> int:
        return 1 if key in self.store else 0

    async def delete(self, key: str) -> int:
        return 1 if self.store.pop(key, None) is not None else 0

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = ex
        return True

    async def incrby(self, key: str, amount: int) -> int:
        cur = int(self.store.get(key, "0"))
        cur += amount
        self.store[key] = str(cur)
        return cur

    async def expire(self, key: str, ttl: int) -> bool:
        if key in self.store:
            self.ttls[key] = ttl
            return True
        return False


@pytest.fixture
def redis(monkeypatch):  # noqa: ANN001
    fake = _FakeRedis()
    monkeypatch.setattr(mod, "get_redis", lambda: fake)
    return fake


def _ctx(tenant_id=None):  # noqa: ANN001
    return TenantContext(
        user_id=uuid4(),
        tenant_id=tenant_id or uuid4(),
        username="t",
        is_superuser=False,
        permissions=frozenset(),
    )


def test_normalize_key_rejects_path_escape():
    with pytest.raises(BadRequestError):
        mod.normalize_relative_key("../etc/passwd")
    with pytest.raises(BadRequestError):
        mod.normalize_relative_key("a b")


@pytest.mark.asyncio
async def test_set_get_delete_scoped_to_tenant(redis):  # noqa: ANN001
    ctx = _ctx()
    out = await mod.run_redis_kv(ctx.tenant_id, {"op": "set", "key": "session/count", "value": "1", "ttl_sec": 60})
    assert out["ok"] is True
    full = RedisKeys.agent_kv(ctx.tenant_id, "session/count")
    assert full in redis.store
    assert not any(k.startswith("agent_kv:") and str(ctx.tenant_id) not in k for k in redis.store)

    got = await mod.run_redis_kv(ctx.tenant_id, {"op": "get", "key": "session/count"})
    assert got["value"] == "1"
    assert got["exists"] is True

    other = _ctx()
    miss = await mod.run_redis_kv(other.tenant_id, {"op": "get", "key": "session/count"})
    assert miss["exists"] is False

    deleted = await mod.run_redis_kv(ctx.tenant_id, {"op": "delete", "key": "session/count"})
    assert deleted["deleted"] is True


@pytest.mark.asyncio
async def test_incr_and_exists(redis):  # noqa: ANN001
    ctx = _ctx()
    await mod.run_redis_kv(ctx.tenant_id, {"op": "incr", "key": "n", "amount": 2})
    out = await mod.run_redis_kv(ctx.tenant_id, {"op": "incr", "key": "n", "amount": 3})
    assert out["value"] == 5
    assert (await mod.run_redis_kv(ctx.tenant_id, {"op": "exists", "key": "n"}))["exists"] is True


@pytest.mark.asyncio
async def test_unknown_op_rejected(redis):  # noqa: ANN001
    with pytest.raises(BadRequestError, match="op"):
        await mod.run_redis_kv(uuid4(), {"op": "flushall", "key": "x"})


@pytest.mark.asyncio
async def test_handler_dispatches(monkeypatch):  # noqa: ANN001
    from miles_portal.tenant.tools.handlers import handlers as h

    async def fake_run(tenant_id, params):  # noqa: ANN001
        return {"op": "get", "tenant": str(tenant_id), "key": params["key"]}

    monkeypatch.setattr("miles_portal.tenant.tools.services.redis_kv.run_redis_kv", fake_run)
    ctx = _ctx()
    out = await h.handle_redis_kv({"op": "get", "key": "a"}, ctx=ctx)
    assert out["tenant"] == str(ctx.tenant_id)
