"""智能体对话 WebSocket 协议与请求构造。"""

import json

import pytest

from app.tenant.agents.ws import protocol as proto
from app.tenant.agents.ws.chat import _build_chat_request
from app.tenant.agents.ws.auth import extract_bearer_token


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
