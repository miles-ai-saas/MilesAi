"""对话 WS Redis 会话快照（R5b）。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from miles_portal.tenant.agents.ws import protocol as proto
from miles_portal.tenant.agents.ws.event_buffer import (
    SessionEventBuffer,
    clear_session_buffers,
    get_session_buffer,
)
from miles_portal.tenant.agents.ws.outbound import WsOutbound
from miles_portal.tenant.agents.ws.redis_snapshot import load_events, persist_event


@pytest.fixture(autouse=True)
def _clear():
    clear_session_buffers()
    yield
    clear_session_buffers()


@pytest.mark.asyncio
async def test_persist_event_rpush_ltrim_expire(monkeypatch):  # noqa: ANN001
    monkeypatch.setattr(
        "miles_portal.tenant.agents.ws.redis_snapshot.get_settings",
        lambda: MagicMock(
            agent_chat_ws_redis_snapshot_enabled=True,
            agent_chat_ws_event_buffer_size=8,
            agent_chat_ws_event_buffer_ttl_sec=60,
        ),
    )
    pipe = MagicMock()
    pipe.rpush = MagicMock()
    pipe.ltrim = MagicMock()
    pipe.expire = MagicMock()
    pipe.execute = AsyncMock(return_value=[1, True, True])
    redis = MagicMock()
    redis.pipeline = MagicMock(return_value=pipe)

    with patch("miles_core.infra.redis.get_redis", return_value=redis):
        env = proto.envelope(proto.CHAT_DELTA, {"text": "hi"})
        await persist_event("t:u:a:c", env)

    pipe.rpush.assert_called_once()
    pipe.ltrim.assert_called_once_with("ws:chat:events:t:u:a:c", -8, -1)
    pipe.expire.assert_called_once_with("ws:chat:events:t:u:a:c", 60)
    pipe.execute.assert_awaited()


@pytest.mark.asyncio
async def test_persist_skipped_when_disabled(monkeypatch):  # noqa: ANN001
    monkeypatch.setattr(
        "miles_portal.tenant.agents.ws.redis_snapshot.get_settings",
        lambda: MagicMock(agent_chat_ws_redis_snapshot_enabled=False),
    )
    with patch("miles_core.infra.redis.get_redis") as get_redis:
        await persist_event("k", proto.envelope(proto.CHAT_DELTA, {"text": "x"}))
        get_redis.assert_not_called()


@pytest.mark.asyncio
async def test_load_events_parses_list(monkeypatch):  # noqa: ANN001
    monkeypatch.setattr(
        "miles_portal.tenant.agents.ws.redis_snapshot.get_settings",
        lambda: MagicMock(agent_chat_ws_redis_snapshot_enabled=True),
    )
    import json

    e1 = proto.envelope(proto.CHAT_DELTA, {"text": "a"})
    redis = MagicMock()
    redis.lrange = AsyncMock(return_value=[json.dumps(e1)])

    with patch("miles_core.infra.redis.get_redis", return_value=redis):
        items = await load_events("sess")
    assert len(items) == 1
    assert items[0]["payload"]["text"] == "a"


@pytest.mark.asyncio
async def test_get_session_buffer_hydrates_from_redis(monkeypatch):  # noqa: ANN001
    monkeypatch.setattr(
        "miles_portal.tenant.agents.ws.event_buffer.get_settings",
        lambda: MagicMock(
            agent_chat_ws_event_buffer_size=32,
            agent_chat_ws_event_buffer_ttl_sec=600,
        ),
    )
    remote = [
        proto.envelope(proto.CHAT_DELTA, {"text": "from-redis"}),
        proto.envelope(proto.CHAT_DONE, {"answer": "from-redis"}),
    ]
    with patch(
        "miles_portal.tenant.agents.ws.redis_snapshot.load_events",
        new=AsyncMock(return_value=remote),
    ):
        buf = await get_session_buffer("hydrate-key")
    assert len(buf.events) == 2
    assert buf.events[0]["payload"]["text"] == "from-redis"


@pytest.mark.asyncio
async def test_outbound_persists_on_record(monkeypatch):  # noqa: ANN001
    called: list[tuple[str, dict]] = []

    async def _persist(key: str, env: dict) -> None:
        called.append((key, env))

    monkeypatch.setattr(
        "miles_portal.tenant.agents.ws.outbound.persist_event",
        _persist,
    )

    class _Ws:
        async def send_json(self, _data):  # noqa: ANN001
            return None

    buf = SessionEventBuffer(max_size=8)
    out = WsOutbound(_Ws(), buf, session_key="sk-1")  # type: ignore[arg-type]
    await out.send(proto.CHAT_DELTA, {"text": "z"})
    assert len(called) == 1
    assert called[0][0] == "sk-1"
    assert called[0][1]["payload"]["text"] == "z"
