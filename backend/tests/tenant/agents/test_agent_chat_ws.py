"""智能体对话 WebSocket 协议与请求构造。"""

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.tenant.agents.schemas.agent import ChatRequest, ChatResponse
from app.tenant.agents.services.agent import AgentService
from app.tenant.agents.ws import protocol as proto
from app.tenant.agents.ws.chat import _build_chat_request, _run_chat_turn
from app.tenant.agents.ws.auth import extract_bearer_token
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
        patch("app.tenant.agents.ws.chat.AsyncSessionLocal", _FakeAsyncSession),
        patch.object(AgentService, "chat", mock_chat),
        patch("app.tenant.agents.ws.chat.proto.send_json", side_effect=fake_send_json),
        patch("app.tenant.agents.ws.chat.proto.emit_answer_deltas", new_callable=AsyncMock) as emit_mock,
        patch("app.tenant.agents.ws.chat.spawn_job_watchers"),
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
