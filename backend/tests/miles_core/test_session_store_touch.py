"""touch_session 节流：短时间内二次 touch 不写 Redis。"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from miles_core.auth import session_store


class _FakeRedis:
    def __init__(self, raw: str | None) -> None:
        self.raw = raw
        self.setex = AsyncMock()
        self.get = AsyncMock(side_effect=lambda _k: self.raw)
        self.ttl = AsyncMock(return_value=3600)


@pytest.mark.asyncio
async def test_touch_skips_when_last_seen_fresh(monkeypatch):
    now = datetime(2026, 9, 22, 12, 0, 0, tzinfo=UTC)
    meta = {
        "jti": "j1",
        "last_seen_at": (now - timedelta(seconds=60)).isoformat(),
        "created_at": now.isoformat(),
    }
    import json

    fake = _FakeRedis(json.dumps(meta))
    monkeypatch.setattr(session_store, "get_redis", AsyncMock(return_value=fake))
    wrote = await session_store.touch_session(uuid4(), "j1", now=now)
    assert wrote is False
    fake.setex.assert_not_awaited()


@pytest.mark.asyncio
async def test_touch_writes_when_stale(monkeypatch):
    now = datetime(2026, 9, 22, 12, 0, 0, tzinfo=UTC)
    meta = {
        "jti": "j1",
        "last_seen_at": (now - timedelta(seconds=400)).isoformat(),
        "created_at": now.isoformat(),
    }
    import json

    fake = _FakeRedis(json.dumps(meta))
    monkeypatch.setattr(session_store, "get_redis", AsyncMock(return_value=fake))
    wrote = await session_store.touch_session(uuid4(), "j1", now=now)
    assert wrote is True
    fake.setex.assert_awaited()
