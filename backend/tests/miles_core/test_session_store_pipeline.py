"""list_sessions / revoke_all_sessions 使用 pipeline / mget，避免逐 jti 往返。"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from miles_common.redis_keys import RedisKeys
from miles_core.auth import session_store


class _Pipe:
    def __init__(self, store: "_StoreRedis") -> None:
        self._store = store
        self._ops: list[tuple] = []

    def get(self, key: str) -> _Pipe:
        self._ops.append(("get", key))
        return self

    def setex(self, key: str, ttl: int, value: str) -> _Pipe:
        self._ops.append(("setex", key, ttl, value))
        return self

    def delete(self, *keys: str) -> _Pipe:
        self._ops.append(("delete", keys))
        return self

    def srem(self, key: str, *members: str) -> _Pipe:
        self._ops.append(("srem", key, members))
        return self

    def sadd(self, key: str, *members: str) -> _Pipe:
        self._ops.append(("sadd", key, members))
        return self

    def expire(self, key: str, ttl: int) -> _Pipe:
        self._ops.append(("expire", key, ttl))
        return self

    async def execute(self) -> list:
        self._store.pipeline_executes += 1
        self._store.pipeline_ops.extend(self._ops)
        out = []
        for op in self._ops:
            kind = op[0]
            if kind == "get":
                out.append(self._store.entries.get(op[1]))
            elif kind == "setex":
                self._store.entries[op[1]] = op[3]
                self._store.ttls[op[1]] = op[2]
                out.append(True)
            elif kind == "delete":
                for k in op[1]:
                    self._store.entries.pop(k, None)
                out.append(1)
            elif kind == "srem":
                s = self._store.indexes.setdefault(op[1], set())
                for m in op[2]:
                    s.discard(m)
                out.append(1)
            elif kind == "sadd":
                s = self._store.indexes.setdefault(op[1], set())
                for m in op[2]:
                    s.add(m)
                out.append(1)
            elif kind == "expire":
                out.append(True)
        return out


class _StoreRedis:
    def __init__(self) -> None:
        self.entries: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.indexes: dict[str, set[str]] = {}
        self.pipeline_executes = 0
        self.pipeline_ops: list[tuple] = []
        self.get = AsyncMock(side_effect=self._get)
        self.smembers = AsyncMock(side_effect=self._smembers)
        self.mget = AsyncMock(side_effect=self._mget)

    async def _get(self, key: str) -> str | None:
        return self.entries.get(key)

    async def _smembers(self, key: str) -> set[str]:
        return set(self.indexes.get(key, set()))

    async def _mget(self, keys: list[str]) -> list[str | None]:
        return [self.entries.get(k) for k in keys]

    def pipeline(self, transaction: bool = False) -> _Pipe:  # noqa: ARG002
        return _Pipe(self)


@pytest.mark.asyncio
async def test_list_sessions_uses_mget_and_batches_stale_srem(monkeypatch):
    user_id = uuid4()
    idx = session_store._index_key(user_id)
    j_alive, j_stale = "alive", "stale"
    fake = _StoreRedis()
    fake.indexes[idx] = {j_alive, j_stale}
    fake.entries[session_store._entry_key(user_id, j_alive)] = json.dumps(
        {"jti": j_alive, "created_at": "2026-09-22T12:00:00+00:00", "last_seen_at": "2026-09-22T12:00:00+00:00"}
    )
    monkeypatch.setattr(session_store, "get_redis", AsyncMock(return_value=fake))

    sessions = await session_store.list_sessions(user_id)

    assert len(sessions) == 1
    assert sessions[0]["jti"] == j_alive
    fake.mget.assert_awaited_once()
    assert j_stale not in fake.indexes[idx]
    assert fake.pipeline_executes >= 1  # stale srem batched


@pytest.mark.asyncio
async def test_revoke_all_sessions_uses_single_pipeline(monkeypatch):
    user_id = uuid4()
    idx = session_store._index_key(user_id)
    fake = _StoreRedis()
    fake.indexes[idx] = {"a", "b", "keep"}
    for j in ("a", "b", "keep"):
        fake.entries[session_store._entry_key(user_id, j)] = json.dumps({"jti": j})
    monkeypatch.setattr(session_store, "get_redis", AsyncMock(return_value=fake))

    revoked = await session_store.revoke_all_sessions(user_id, keep_jti="keep")

    assert revoked == 2
    assert fake.pipeline_executes == 1
    assert "keep" in fake.indexes[idx]
    assert "a" not in fake.indexes[idx]
    assert RedisKeys.token_blacklist("a") in fake.entries
    assert RedisKeys.token_blacklist("b") in fake.entries
    assert RedisKeys.token_blacklist("keep") not in fake.entries
