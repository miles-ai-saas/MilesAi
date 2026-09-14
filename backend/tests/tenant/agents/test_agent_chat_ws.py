"""智能体对话 WebSocket 协议与请求构造。"""

import asyncio
import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import WebSocketDisconnect

from miles_common.exceptions import UnauthorizedError
from miles_core.config import get_settings
from miles_portal.tenant.agents.schemas.agent import ChatRequest, ChatResponse
from miles_portal.tenant.agents.services.agent import AgentService
from miles_portal.tenant.agents.ws import protocol as proto
from miles_portal.tenant.agents.ws.auth import extract_bearer_token
from miles_portal.tenant.agents.ws.chat import _build_chat_request, _run_chat_turn, agent_chat_websocket
from tests.conftest import make_tenant_ctx


class _FakeWebSocket:
    def __init__(self, query: str = "", authorization: str = ""):
        self.query_params = {}
        if query:
            for part in query.split("&"):
                k, _, v = part.partition("=")
                self.query_params[k] = v
        self.headers = {"authorization": authorization} if authorization else {}


def test_parse_client_frame_chat_send():
    raw = json.dumps({"type": "chat.send", "payload": {"query": "你好"}})
    event_type, payload = proto.parse_client_frame(raw)
    assert event_type == "chat.send"
    assert payload["query"] == "你好"


def test_build_chat_request_media_and_conversation():
    body = _build_chat_request(
        {
            "query": "看图",
            "media": [{"attachment_id": "550e8400-e29b-41d4-a716-446655440000"}],
        },
        conversation_id="conv-1",
    )
    assert body.conversation_id == "conv-1"
    assert len(body.media) == 1


def test_build_chat_request_generative_params():
    """WS 补齐生图/生视频参数，与 HTTP 路径对齐。"""
    body = _build_chat_request(
        {
            "query": "画一只猫",
            "generative_image_n": 3,
            "generative_video_duration": 10,
        },
        conversation_id="conv-2",
    )
    assert body.generative_image_n == 3
    assert body.generative_video_duration == 10


def test_build_chat_request_generative_params_defaults():
    """不传生成参数时使用 ChatRequest 的 field default。"""
    body = _build_chat_request(
        {"query": "你好"},
        conversation_id="conv-3",
    )
    assert body.generative_image_n == 1
    assert body.generative_video_duration == 5


def test_build_chat_request_tool_confirm():
    body = _build_chat_request(
        {
            "query": "确认执行工具",
            "tool_confirmed": True,
            "pending_tool_slug": "search",
            "pending_tool_params": {"q": "test"},
        },
        conversation_id="conv-4",
    )
    assert body.tool_confirmed is True
    assert body.pending_tool_slug == "search"
    assert body.pending_tool_params == {"q": "test"}


def test_extract_bearer_from_query():
    ws = _FakeWebSocket(query="token=abc123")
    assert extract_bearer_token(ws) == "abc123"


def test_extract_bearer_from_header():
    ws = _FakeWebSocket(authorization="Bearer jwt-here")
    assert extract_bearer_token(ws) == "jwt-here"


@pytest.mark.asyncio
async def test_emit_answer_deltas_chunks():
    sent: list[dict] = []

    class FakeWs:
        async def send_json(self, data):
            sent.append(data)

    await proto.emit_answer_deltas(FakeWs(), "abcdefgh", chunk_size=3)
    texts = [s["payload"]["text"] for s in sent if s["type"] == proto.CHAT_DELTA]
    assert "".join(texts) == "abcdefgh"


class _FakeAsyncSession:
    async def __aenter__(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        return db

    async def __aexit__(self, *args):
        return None


@pytest.mark.asyncio
async def test_run_chat_turn_skips_emit_answer_deltas_when_streamed():
    """已推送 token delta 时不再整段切块。"""
    sent: list[tuple[str, dict]] = []

    async def fake_send_json(_ws, event_type, payload):
        sent.append((event_type, payload))

    async def mock_chat(_self, _agent_id, _body, *, on_delta=None):
        if on_delta:
            await on_delta("a")
        return ChatResponse(answer="a")

    with (
        patch("miles_portal.tenant.agents.ws.chat.AsyncSessionLocal", _FakeAsyncSession),
        patch.object(AgentService, "chat", mock_chat),
        patch("miles_portal.tenant.agents.ws.chat.proto.send_json", side_effect=fake_send_json),
        patch("miles_portal.tenant.agents.ws.chat.proto.emit_answer_deltas", new_callable=AsyncMock) as emit_mock,
        patch("miles_portal.tenant.agents.ws.chat.spawn_job_watchers"),
    ):
        await _run_chat_turn(
            AsyncMock(),
            make_tenant_ctx(),
            uuid4(),
            ChatRequest(query="hi"),
            set(),
        )

    delta_texts = [p["text"] for t, p in sent if t == proto.CHAT_DELTA]
    assert delta_texts == ["a"]
    emit_mock.assert_not_called()
    done_payloads = [p for t, p in sent if t == proto.CHAT_DONE]
    assert len(done_payloads) == 1
    assert done_payloads[0]["answer"] == "a"


# --------------------------------------------------------------------------- #
# agent_chat_websocket 端点
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _ScriptedWebSocket:
    """按脚本喂帧的 WebSocket 假件；帧用尽即抛 WebSocketDisconnect。"""

    def __init__(self, frames: list[str] | None = None, *, authorization: str = ""):
        self.frames = list(frames or [])
        self.query_params: dict[str, str] = {}
        self.headers = {"authorization": authorization} if authorization else {}
        self.accepted = False
        self.closed: list[tuple[int, str]] = []
        self.sent: list[dict] = []

    async def accept(self) -> None:
        self.accepted = True

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed.append((code, reason))

    async def receive_text(self) -> str:
        if self.frames:
            return self.frames.pop(0)
        raise WebSocketDisconnect()

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)

    def payloads(self, event_type: str) -> list[dict]:
        return [s["payload"] for s in self.sent if s["type"] == event_type]

    @property
    def sent_types(self) -> list[str]:
        return [s["type"] for s in self.sent]


class _RecordingSession:
    """可检视 commit/rollback 的 session 假件。"""

    def __init__(self) -> None:
        self.db = AsyncMock()

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *args):
        return None


def _frame(event_type: str, payload: dict | None = None) -> str:
    return json.dumps({"type": event_type, "payload": payload or {}})


@contextmanager
def _connected(ctx=None):  # noqa: ANN001
    """已通过鉴权的连接环境；yield 出可检视的 session。

    令牌解析另有 tests/tenant/agents/test_agent_chat_ws.py 中的
    test_extract_bearer_from_query / _header 覆盖，此处直接给定结果。
    """
    session = _RecordingSession()
    with (
        patch("miles_portal.tenant.agents.ws.chat.AsyncSessionLocal", lambda: session),
        patch("miles_portal.tenant.agents.ws.chat.extract_bearer_token", lambda _ws: "tok"),
        patch(
            "miles_portal.tenant.agents.ws.chat.resolve_tenant_context",
            AsyncMock(return_value=ctx if ctx is not None else make_tenant_ctx(permissions=frozenset(["agent:read"]))),
        ),
    ):
        yield session


async def test_ws_disabled_closes_4403(monkeypatch):
    monkeypatch.setenv("AGENT_CHAT_WEBSOCKET_ENABLED", "false")
    ws = _ScriptedWebSocket()

    await agent_chat_websocket(ws, uuid4(), conversation_id="c1")

    assert ws.closed == [(4403, "WebSocket disabled")]
    assert ws.accepted is False


async def test_ws_missing_token_closes_4401():
    ws = _ScriptedWebSocket()

    await agent_chat_websocket(ws, uuid4(), conversation_id="c1")

    assert ws.closed == [(4401, "Missing token")]
    assert ws.accepted is False


async def test_ws_unauthorized_closes_4401():
    ws = _ScriptedWebSocket(authorization="Bearer t")
    session = _RecordingSession()
    with (
        patch("miles_portal.tenant.agents.ws.chat.AsyncSessionLocal", lambda: session),
        patch(
            "miles_portal.tenant.agents.ws.chat.resolve_tenant_context",
            AsyncMock(side_effect=UnauthorizedError("nope")),
        ),
    ):
        await agent_chat_websocket(ws, uuid4(), conversation_id="c1")

    assert ws.closed == [(4401, "Unauthorized")]
    assert ws.accepted is False


async def test_ws_auth_failure_closes_4500():
    ws = _ScriptedWebSocket(authorization="Bearer t")
    session = _RecordingSession()
    with (
        patch("miles_portal.tenant.agents.ws.chat.AsyncSessionLocal", lambda: session),
        patch(
            "miles_portal.tenant.agents.ws.chat.resolve_tenant_context",
            AsyncMock(side_effect=RuntimeError("boom")),
        ),
    ):
        await agent_chat_websocket(ws, uuid4(), conversation_id="c1")

    assert ws.closed == [(4500, "Auth error")]
    assert ws.accepted is False


async def test_ws_ping_replies_pong():
    ws = _ScriptedWebSocket([_frame(proto.PING)])
    with _connected():
        await agent_chat_websocket(ws, uuid4(), conversation_id="c1")

    assert ws.accepted is True
    assert ws.sent_types == [proto.PONG]
    assert ws.closed == []


async def test_ws_invalid_frame_reports_error():
    ws = _ScriptedWebSocket(["not-json"])
    with _connected():
        await agent_chat_websocket(ws, uuid4(), conversation_id="c1")

    assert ws.sent_types == [proto.CHAT_ERROR]
    assert ws.payloads(proto.CHAT_ERROR)


async def test_ws_unknown_type_reports_error():
    ws = _ScriptedWebSocket([_frame("nope")])
    with _connected():
        await agent_chat_websocket(ws, uuid4(), conversation_id="c1")

    assert ws.payloads(proto.CHAT_ERROR)[0]["message"] == "未知 type: nope"


async def test_ws_tool_confirm_is_dispatched_as_chat_send():
    seen: list[ChatRequest] = []

    async def fake_turn(_ws, _ctx, _agent_id, body, _job_tasks):
        seen.append(body)

    ws = _ScriptedWebSocket([_frame(proto.TOOL_CONFIRM, {"pending_tool_slug": "search"})])
    with (
        _connected(),
        patch("miles_portal.tenant.agents.ws.chat._run_chat_turn", fake_turn),
    ):
        await agent_chat_websocket(ws, uuid4(), conversation_id="c1")

    assert len(seen) == 1
    assert seen[0].tool_confirmed is True
    assert seen[0].query == "确认执行工具"
    assert ws.sent_types == []


async def test_ws_invalid_chat_request_reports_error():
    payload = {"query": "x", "media": [{"attachment_id": "not-a-uuid"}]}
    ws = _ScriptedWebSocket([_frame(proto.CHAT_SEND, payload)])
    with _connected():
        await agent_chat_websocket(ws, uuid4(), conversation_id="c1")

    assert ws.payloads(proto.CHAT_ERROR)[0]["message"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("generative_image_n", "abc"),
        ("generative_video_duration", "abc"),
        ("generative_image_n", []),
        ("generative_video_duration", {"a": 1}),
    ],
)
async def test_ws_non_numeric_generative_field_reports_error_instead_of_crashing(field, value):
    """回归：整数字段在 pydantic 校验之前先被强转，非法值会绕过 ``except ValidationError``。

    ``int("abc")`` 抛 ValueError、``int([])`` 抛 TypeError，都不在原先只捕
    ``ValidationError`` 的范围内，会穿透整个 ws 端点，让客户端只看到连接被异常关闭，
    而不是像其它非法输入那样收到 ``chat.error``。
    """
    ws = _ScriptedWebSocket([_frame(proto.CHAT_SEND, {"query": "hi", field: value})])
    with _connected():
        await agent_chat_websocket(ws, uuid4(), conversation_id="c1")

    assert ws.sent_types == [proto.CHAT_ERROR]
    assert field in ws.payloads(proto.CHAT_ERROR)[0]["message"]
    assert ws.closed == []  # 连接不该因此被异常关闭


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("inputs", "abc"),
        ("pending_tool_params", "ab"),
        ("inputs", [1, 2]),
    ],
)
async def test_ws_non_object_dict_field_reports_error_instead_of_crashing(field, value):
    """回归：``dict("abc")`` 抛的 ``dictionary update sequence element ...`` 既穿透端点又难懂。"""
    ws = _ScriptedWebSocket([_frame(proto.CHAT_SEND, {"query": "hi", field: value})])
    with _connected():
        await agent_chat_websocket(ws, uuid4(), conversation_id="c1")

    assert ws.sent_types == [proto.CHAT_ERROR]
    assert field in ws.payloads(proto.CHAT_ERROR)[0]["message"]
    assert ws.closed == []


@pytest.mark.parametrize("field", ["generative_image_n", "generative_video_duration"])
async def test_ws_null_generative_field_falls_back_to_default(field):
    """显式传 null 视作「未提供」，沿用 ChatRequest 的 field default（非报错）。"""
    seen: list[ChatRequest] = []

    async def fake_turn(_ws, _ctx, _agent_id, body, _job_tasks):
        seen.append(body)

    ws = _ScriptedWebSocket([_frame(proto.CHAT_SEND, {"query": "hi", field: None})])
    with (
        _connected(),
        patch("miles_portal.tenant.agents.ws.chat._run_chat_turn", fake_turn),
    ):
        await agent_chat_websocket(ws, uuid4(), conversation_id="c1")

    assert len(seen) == 1
    assert seen[0].generative_image_n == 1
    assert seen[0].generative_video_duration == 5


@pytest.mark.parametrize("field", ["inputs", "pending_tool_params"])
async def test_ws_null_dict_field_becomes_empty_dict(field):
    seen: list[ChatRequest] = []

    async def fake_turn(_ws, _ctx, _agent_id, body, _job_tasks):
        seen.append(body)

    ws = _ScriptedWebSocket([_frame(proto.CHAT_SEND, {"query": "hi", field: None})])
    with (
        _connected(),
        patch("miles_portal.tenant.agents.ws.chat._run_chat_turn", fake_turn),
    ):
        await agent_chat_websocket(ws, uuid4(), conversation_id="c1")

    assert len(seen) == 1
    assert getattr(seen[0], field) == {}


async def test_ws_chat_send_dispatches_turn():
    seen: list[tuple] = []

    async def fake_turn(_ws, _ctx, agent_id, body, _job_tasks):
        seen.append((agent_id, body.conversation_id))

    agent_id = uuid4()
    ws = _ScriptedWebSocket([_frame(proto.CHAT_SEND, {"query": "hi"})])
    with (
        _connected(),
        patch("miles_portal.tenant.agents.ws.chat._run_chat_turn", fake_turn),
    ):
        await agent_chat_websocket(ws, agent_id, conversation_id="conv-9")

    assert seen == [(agent_id, "conv-9")]


async def test_ws_job_cancel_without_id_reports_error():
    ws = _ScriptedWebSocket([_frame(proto.GENERATIVE_JOB_CANCEL, {})])
    with _connected():
        await agent_chat_websocket(ws, uuid4(), conversation_id="c1")

    assert ws.payloads(proto.CHAT_ERROR)[0]["message"] == "缺少 job_id"


async def test_ws_job_cancel_invalid_id_reports_error():
    ws = _ScriptedWebSocket([_frame(proto.GENERATIVE_JOB_CANCEL, {"job_id": "not-a-uuid"})])
    with _connected():
        await agent_chat_websocket(ws, uuid4(), conversation_id="c1")

    assert ws.payloads(proto.CHAT_ERROR)[0]["message"] == "无效 job_id"


async def test_ws_job_cancel_success_commits_and_pushes_progress():
    out = SimpleNamespace(model_dump=lambda **_: {"id": "j1", "status": "cancelled"})
    ws = _ScriptedWebSocket([_frame(proto.GENERATIVE_JOB_CANCEL, {"job_id": str(uuid4())})])
    with (
        _connected() as session,
        patch("miles_portal.tenant.agents.ws.chat.cancel_generative_job_ws", AsyncMock(return_value=out)),
    ):
        await agent_chat_websocket(ws, uuid4(), conversation_id="c1")

    assert ws.payloads(proto.GENERATIVE_JOB_PROGRESS) == [{"id": "j1", "status": "cancelled"}]
    session.db.commit.assert_awaited()
    session.db.rollback.assert_not_awaited()


async def test_ws_job_cancel_failure_rolls_back_and_reports_error():
    ws = _ScriptedWebSocket([_frame(proto.GENERATIVE_JOB_CANCEL, {"job_id": str(uuid4())})])
    with (
        _connected() as session,
        patch(
            "miles_portal.tenant.agents.ws.chat.cancel_generative_job_ws",
            AsyncMock(side_effect=RuntimeError("取消失败")),
        ),
    ):
        await agent_chat_websocket(ws, uuid4(), conversation_id="c1")

    assert ws.payloads(proto.CHAT_ERROR)[0]["message"] == "取消失败"
    session.db.rollback.assert_awaited()
    session.db.commit.assert_not_awaited()


async def test_ws_disconnect_cancels_spawned_job_tasks():
    created: list[asyncio.Task] = []

    async def fake_turn(_ws, _ctx, _agent_id, _body, job_tasks):
        # 用有限 sleep 而非永久等待：万一没被取消，gather 仍会返回，
        # 断言给出失败而不是把测试挂死。
        task = asyncio.create_task(asyncio.sleep(5))
        job_tasks.add(task)
        created.append(task)

    ws = _ScriptedWebSocket([_frame(proto.CHAT_SEND, {"query": "hi"})])
    with (
        _connected(),
        patch("miles_portal.tenant.agents.ws.chat._run_chat_turn", fake_turn),
    ):
        await agent_chat_websocket(ws, uuid4(), conversation_id="c1")

    assert len(created) == 1
    assert created[0].cancelled()
