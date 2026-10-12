"""对话 WS 事件环缓与断线重放。"""

from uuid import uuid4

import pytest

from miles_portal.tenant.agents.ws import protocol as proto
from miles_portal.tenant.agents.ws.event_buffer import (
    SessionEventBuffer,
    clear_session_buffers,
    get_session_buffer,
    session_key,
)
from miles_portal.tenant.agents.ws.outbound import WsOutbound, reset_outbound, set_outbound
from miles_portal.tenant.agents.ws.chat import agent_chat_websocket
from tests.conftest import make_tenant_ctx
from tests.miles_portal.tenant.agents.test_agent_chat_ws import _ScriptedWebSocket, _connected, _frame


@pytest.fixture(autouse=True)
def _clear_buffers():
    clear_session_buffers()
    yield
    clear_session_buffers()


def test_events_after_replay_and_gap():
    buf = SessionEventBuffer(max_size=8)
    e1 = proto.envelope(proto.CHAT_DELTA, {"text": "a"})
    e2 = proto.envelope(proto.CHAT_DELTA, {"text": "b"})
    e3 = proto.envelope(proto.CHAT_DONE, {"answer": "ab"})
    buf.append(e1)
    buf.append(e2)
    buf.append(e3)

    missed, gap = buf.events_after(e1["id"])
    assert gap is False
    assert [m["payload"]["text"] for m in missed if m["type"] == proto.CHAT_DELTA] == ["b"]
    assert missed[-1]["type"] == proto.CHAT_DONE

    missed2, gap2 = buf.events_after("missing-id")
    assert gap2 is True
    assert missed2 == []

    empty, gap3 = buf.events_after(None)
    assert empty == [] and gap3 is False


def test_ring_buffer_drops_oldest():
    buf = SessionEventBuffer(max_size=2)
    for i in range(3):
        buf.append(proto.envelope(proto.CHAT_DELTA, {"text": str(i)}))
    assert len(buf.events) == 2
    assert buf.events[0]["payload"]["text"] == "1"


@pytest.mark.asyncio
async def test_ws_reconnect_replays_after_last_event_id():
    ctx = make_tenant_ctx(permissions=frozenset(["agent:read"]))
    agent_id = uuid4()
    key = session_key(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        agent_id=agent_id,
        conversation_id="conv-resume",
    )
    buf = get_session_buffer(key)
    e1 = proto.envelope(proto.CHAT_DELTA, {"text": "已收"})
    e2 = proto.envelope(proto.CHAT_DELTA, {"text": "续"})
    e3 = proto.envelope(proto.CHAT_DONE, {"answer": "已收续"})
    buf.append(e1)
    buf.append(e2)
    buf.append(e3)

    ws = _ScriptedWebSocket([_frame(proto.PING)])
    with _connected(ctx):
        await agent_chat_websocket(
            ws,
            agent_id,
            conversation_id="conv-resume",
            last_event_id=e1["id"],
        )

    assert ws.sent_types[0] == proto.CHAT_SYNC
    sync = ws.payloads(proto.CHAT_SYNC)[0]
    assert sync["gap"] is False
    assert sync["replayed"] == 2
    assert ws.sent_types[1:3] == [proto.CHAT_DELTA, proto.CHAT_DONE]
    assert ws.payloads(proto.CHAT_DELTA)[0]["text"] == "续"
    assert ws.sent_types[-1] == proto.PONG


@pytest.mark.asyncio
async def test_ws_reconnect_reports_gap_when_id_missing():
    ctx = make_tenant_ctx(permissions=frozenset(["agent:read"]))
    agent_id = uuid4()
    key = session_key(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        agent_id=agent_id,
        conversation_id="conv-gap",
    )
    buf = get_session_buffer(key)
    buf.append(proto.envelope(proto.CHAT_DELTA, {"text": "x"}))

    ws = _ScriptedWebSocket()
    with _connected(ctx):
        await agent_chat_websocket(
            ws,
            agent_id,
            conversation_id="conv-gap",
            last_event_id="not-in-buffer",
        )

    sync = ws.payloads(proto.CHAT_SYNC)[0]
    assert sync["gap"] is True
    assert sync["replayed"] == 0
    assert proto.CHAT_DELTA not in ws.sent_types


@pytest.mark.asyncio
async def test_outbound_buffers_even_when_send_fails():
    class _DeadWs:
        async def send_json(self, _data):  # noqa: ANN001
            raise RuntimeError("gone")

    buf = SessionEventBuffer(max_size=16)
    out = WsOutbound(_DeadWs(), buf)  # type: ignore[arg-type]
    token = set_outbound(out)
    try:
        await proto.send_json(_DeadWs(), proto.CHAT_DELTA, {"text": "z"})  # type: ignore[arg-type]
    finally:
        reset_outbound(token)

    assert out.alive is False
    assert len(buf.events) == 1
    assert buf.events[0]["payload"]["text"] == "z"
