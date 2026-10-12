"""A2A ``tasks/pushNotificationConfig/*``。"""

from __future__ import annotations

from uuid import uuid4

import pytest

from miles_core.tenant import TenantContext
from miles_portal.tenant.a2a import server as server_mod
from miles_portal.tenant.a2a.server import build_agent_card
from miles_portal.tenant.a2a.services import server as server_svc
from miles_portal.tenant.a2a.services import push_store
from tests.miles_portal.tenant.a2a.test_a2a_server_card import AGENT_ID, BASE, _Db, _agent, _job


class _FakeRedisHash:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, str]] = {}

    async def hlen(self, key: str) -> int:
        return len(self._data.get(key, {}))

    async def hexists(self, key: str, field: str) -> bool:
        return field in self._data.get(key, {})

    async def hset(self, key: str, field: str, value: str) -> int:
        self._data.setdefault(key, {})[field] = value
        return 1

    async def expire(self, key: str, _ttl: int) -> bool:
        return key in self._data

    async def hget(self, key: str, field: str) -> str | None:
        return self._data.get(key, {}).get(field)

    async def hgetall(self, key: str) -> dict[str, str]:
        return dict(self._data.get(key, {}))

    async def hdel(self, key: str, field: str) -> int:
        bucket = self._data.get(key)
        if not bucket or field not in bucket:
            return 0
        del bucket[field]
        return 1

    async def delete(self, key: str) -> int:
        return 1 if self._data.pop(key, None) is not None else 0


@pytest.fixture
def fake_redis(monkeypatch):  # noqa: ANN001
    redis = _FakeRedisHash()
    monkeypatch.setattr(push_store, "get_redis", lambda: redis)
    return redis


def _ctx() -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="a2a",
        is_superuser=False,
        permissions=frozenset(),
    )


def test_card_declares_push_notifications():
    card = build_agent_card(agent_id=AGENT_ID, name="n", description="d", base_url=BASE)
    assert card["capabilities"]["pushNotifications"] is True


@pytest.mark.asyncio
async def test_push_config_set_get_list_delete(fake_redis, monkeypatch):  # noqa: ANN001
    ctx = _ctx()
    job = _job("running", agent_id=AGENT_ID)
    job.tenant_id = ctx.tenant_id

    async def fake_get(_db, _ctx, _job_id):  # noqa: ANN001
        return job

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", fake_get)

    set_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tasks/pushNotificationConfig/set",
        "params": {
            "taskId": str(job.id),
            "pushNotificationConfig": {
                "url": "https://peer.example.com/hook",
                "id": "cfg-1",
                "token": "secret",
                "authentication": {"schemes": ["Bearer"], "credentials": "tok"},
            },
        },
    }
    env = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), ctx, AGENT_ID, set_payload, base_url=BASE)
    assert "error" not in env
    assert env["result"]["taskId"] == str(job.id)
    assert env["result"]["pushNotificationConfig"]["id"] == "cfg-1"
    assert env["result"]["pushNotificationConfig"]["url"] == "https://peer.example.com/hook"

    get_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tasks/pushNotificationConfig/get",
        "params": {"id": str(job.id), "pushNotificationConfigId": "cfg-1"},
    }
    env2 = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), ctx, AGENT_ID, get_payload, base_url=BASE)
    assert env2["result"]["pushNotificationConfig"]["token"] == "secret"

    list_payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tasks/pushNotificationConfig/list",
        "params": {"id": str(job.id)},
    }
    env3 = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), ctx, AGENT_ID, list_payload, base_url=BASE)
    assert len(env3["result"]) == 1

    del_payload = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tasks/pushNotificationConfig/delete",
        "params": {"id": str(job.id), "pushNotificationConfigId": "cfg-1"},
    }
    env4 = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), ctx, AGENT_ID, del_payload, base_url=BASE)
    assert env4["result"] is None

    env5 = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), ctx, AGENT_ID, list_payload, base_url=BASE)
    assert env5["result"] == []


@pytest.mark.asyncio
async def test_push_config_rejects_bad_url(fake_redis, monkeypatch):  # noqa: ANN001
    ctx = _ctx()
    job = _job("running", agent_id=AGENT_ID)
    job.tenant_id = ctx.tenant_id

    async def fake_get(_db, _ctx, _job_id):  # noqa: ANN001
        return job

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", fake_get)
    monkeypatch.setenv("OUTBOUND_ALLOW_PRIVATE_HOSTS", "false")
    from miles_core.config import get_settings

    get_settings.cache_clear()

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tasks/pushNotificationConfig/set",
        "params": {
            "taskId": str(job.id),
            "pushNotificationConfig": {"url": "http://127.0.0.1/hook"},
        },
    }
    try:
        env = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), ctx, AGENT_ID, payload, base_url=BASE)
        assert env["error"]["code"] == server_mod.INVALID_PARAMS
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_push_config_task_not_owned(fake_redis, monkeypatch):  # noqa: ANN001
    job = _job("running", agent_id=uuid4())

    async def fake_get(_db, _ctx, _job_id):  # noqa: ANN001
        return job

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", fake_get)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tasks/pushNotificationConfig/list",
        "params": {"id": str(job.id)},
    }
    env = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), _ctx(), AGENT_ID, payload, base_url=BASE)
    assert env["error"]["code"] == server_mod.TASK_NOT_FOUND
