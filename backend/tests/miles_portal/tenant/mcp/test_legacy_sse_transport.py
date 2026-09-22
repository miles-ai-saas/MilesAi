"""``legacy_sse_json_rpc`` 的端到端特征化测试。

该函数此前零覆盖（仅 ``_assert_same_origin`` / ``_json_from_sse_data`` 两个纯函数被测），
而它内部的两个闭包 ``sse_reader`` / ``rpc_roundtrip`` 承载了 endpoint 解析、id 配对、
超时与 HTTP 错误处理等全部关键逻辑。本文件先以假 MCP 服务端锁定端到端行为，
作为把闭包外提为可独立测试单元的改造安全网。
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from miles_common.exceptions import BadRequestError
from miles_exec.mcp.constants import MCP_SESSION_HEADER
from miles_portal.tenant.mcp import sse_transport as sse

# 假 Client.post 的形参必须叫 json 才能收关键字实参，故用别名避免遮蔽模块 json
_dumps = json.dumps

SSE_URL = "https://mcp.example.com/sse"
POST_URL = "https://mcp.example.com/messages?session=abc"

_EOS = object()


class _PostResp:
    def __init__(self, status_code: int, text: str = "{}") -> None:
        self.status_code = status_code
        self.text = text


class _FakeServer:
    """最小 MCP SSE 服务端。

    先发 ``endpoint`` 事件；之后每收到一个带 id 的 POST，就把同 id 的 ``message``
    事件放入队列，由 SSE 读循环取出并唤醒等待的 Future。
    """

    def __init__(
        self,
        *,
        endpoint_data: str | None = "/messages?session=abc",
        endpoint_event: str | None = "endpoint",
        init_result=None,
        call_result=None,
        post_status: int | dict[str, int] = 200,
        respond_to_messages: bool = True,
        decoy_id: int | None = None,
        error_methods: set[str] | None = None,
    ) -> None:
        self.endpoint_data = endpoint_data
        self.endpoint_event = endpoint_event
        self.init_result = {"protocolVersion": "2024-11-05"} if init_result is None else init_result
        self.call_result = {"ok": True} if call_result is None else call_result
        self.post_status = post_status
        self.respond_to_messages = respond_to_messages
        self.decoy_id = decoy_id
        self.error_methods = error_methods or set()
        self.queue: asyncio.Queue = asyncio.Queue()
        self.posts: list[dict] = []
        self.sse_headers: dict | None = None

    def _envelope(self, body: dict, rid: int) -> dict:
        if body.get("method") in self.error_methods:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32000, "message": "boom"}}
        result = self.init_result if body.get("method") == "initialize" else self.call_result
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    # --- 假 httpx.AsyncClient ---
    def client_factory(self):
        server = self

        class _Client:
            def __init__(self, **kwargs) -> None:  # noqa: ARG002
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):  # noqa: ARG002
                server.queue.put_nowait(_EOS)
                return False

            async def post(self, url, json=None, headers=None):  # noqa: A002
                body = json or {}
                server.posts.append({"url": url, "body": body, "headers": headers or {}})
                status = server.post_status.get(body.get("method"), 200) if isinstance(server.post_status, dict) else server.post_status
                if status >= 400:
                    return _PostResp(status, "server error")
                rid = body.get("id")
                if rid is None:  # 通知无 id，服务端不回 message
                    return _PostResp(200)
                if server.decoy_id is not None:
                    decoy = {"jsonrpc": "2.0", "id": server.decoy_id, "result": {"decoy": True}}
                    server.queue.put_nowait(SimpleNamespace(event="message", data=_dumps(decoy)))
                if server.respond_to_messages:
                    envelope = server._envelope(body, rid)
                    server.queue.put_nowait(SimpleNamespace(event="message", data=_dumps(envelope)))
                return _PostResp(200)

        return _Client

    # --- 假 aconnect_sse ---
    def connect_sse(self, *args, **kwargs):  # noqa: ARG002
        server = self
        server.sse_headers = kwargs.get("headers")

        class _Ctx:
            async def __aenter__(self):
                return server.event_source()

            async def __aexit__(self, *args):  # noqa: ARG002
                return False

        return _Ctx()

    def event_source(self):
        server = self

        class _ES:
            response = SimpleNamespace(raise_for_status=lambda: None)

            async def aiter_sse(self):
                if server.endpoint_event is not None:
                    yield SimpleNamespace(event=server.endpoint_event, data=server.endpoint_data)
                while True:
                    item = await server.queue.get()
                    if item is _EOS:
                        return
                    yield item

        return _ES()


def _install(monkeypatch, server: _FakeServer) -> None:
    monkeypatch.setattr(sse.httpx, "AsyncClient", server.client_factory())
    monkeypatch.setattr(sse, "aconnect_sse", server.connect_sse)


# --- 正常流程 ---------------------------------------------------------------


async def test_initializes_then_calls_method(monkeypatch):
    server = _FakeServer()
    _install(monkeypatch, server)

    out = await sse.legacy_sse_json_rpc(SSE_URL, "tools/list", {}, timeout=5.0, connect_timeout=5.0)

    assert out == {"ok": True}
    assert [p["body"]["method"] for p in server.posts] == ["initialize", "notifications/initialized", "tools/list"]
    assert server.posts[1]["body"].get("id") is None  # 通知不带 id
    assert all(p["url"] == POST_URL for p in server.posts)


async def test_skips_initialize_when_disabled(monkeypatch):
    server = _FakeServer()
    _install(monkeypatch, server)

    await sse.legacy_sse_json_rpc(
        SSE_URL,
        "tools/list",
        {},
        connection_config={"mcp_initialize": False},
        timeout=5.0,
        connect_timeout=5.0,
    )

    assert [p["body"]["method"] for p in server.posts] == ["tools/list"]


async def test_sends_protocol_headers_and_passthrough_custom_headers(monkeypatch):
    server = _FakeServer()
    _install(monkeypatch, server)

    await sse.legacy_sse_json_rpc(
        SSE_URL,
        "tools/list",
        {},
        connection_config={"session_id": "sess-1", "headers": {"X-Custom": "v"}},
        timeout=5.0,
        connect_timeout=5.0,
    )

    post_headers = server.posts[0]["headers"]
    assert post_headers["Content-Type"] == "application/json"
    assert post_headers["Accept"] == "application/json, text/event-stream"
    assert post_headers["X-Custom"] == "v"
    # legacy SSE 的 session 由 endpoint URL 承载（与 streamable HTTP 用请求头不同）
    assert MCP_SESSION_HEADER not in post_headers
    assert server.posts[0]["url"] == POST_URL
    # GET 只接受事件流
    assert server.sse_headers is not None
    assert server.sse_headers["Accept"] == "text/event-stream"
    assert server.sse_headers["X-Custom"] == "v"


async def test_ignores_message_events_with_unrelated_id(monkeypatch):
    server = _FakeServer(decoy_id=999_999)
    _install(monkeypatch, server)

    out = await sse.legacy_sse_json_rpc(SSE_URL, "tools/list", {}, timeout=5.0, connect_timeout=5.0)
    assert out == {"ok": True}


async def test_notification_failure_only_warns(monkeypatch):
    server = _FakeServer(post_status={"notifications/initialized": 500})
    _install(monkeypatch, server)

    out = await sse.legacy_sse_json_rpc(SSE_URL, "tools/list", {}, timeout=5.0, connect_timeout=5.0)
    assert out == {"ok": True}  # 通知失败不阻断


# --- 失败路径 ---------------------------------------------------------------


async def test_raises_when_endpoint_event_never_arrives(monkeypatch):
    server = _FakeServer(endpoint_event=None)
    _install(monkeypatch, server)

    with pytest.raises(BadRequestError) as ei:
        await sse.legacy_sse_json_rpc(SSE_URL, "tools/list", {}, timeout=5.0, connect_timeout=0.05)
    assert "未在" in str(ei.value)


async def test_raises_on_post_http_error(monkeypatch):
    server = _FakeServer(post_status=500)
    _install(monkeypatch, server)

    with pytest.raises(BadRequestError) as ei:
        await sse.legacy_sse_json_rpc(SSE_URL, "tools/list", {}, timeout=5.0, connect_timeout=5.0)
    assert "MCP POST 500" in str(ei.value)


async def test_raises_on_response_timeout(monkeypatch):
    server = _FakeServer(respond_to_messages=False)
    _install(monkeypatch, server)

    with pytest.raises(BadRequestError) as ei:
        await sse.legacy_sse_json_rpc(SSE_URL, "tools/list", {}, timeout=0.05, connect_timeout=5.0)
    assert "响应超时" in str(ei.value)


async def test_cross_origin_endpoint_reports_ssrf_rejection_instead_of_timeout(monkeypatch):
    """跨域 endpoint 必须报出「不同源」这一真实原因，且不等满 connect_timeout。

    回归：该异常发生在尚无等待方时被读循环的兜底 except 吞掉，此前只表现为
    endpoint 等待超时（connect_timeout 设 5s 就要白等 5s）。
    """
    server = _FakeServer(endpoint_data="https://evil.example.com/messages")
    _install(monkeypatch, server)

    started = asyncio.get_running_loop().time()
    with pytest.raises(BadRequestError) as ei:
        await sse.legacy_sse_json_rpc(SSE_URL, "tools/list", {}, timeout=5.0, connect_timeout=5.0)
    elapsed = asyncio.get_running_loop().time() - started

    assert "不同源" in str(ei.value)
    assert elapsed < 1.0  # 关键：不白等满 connect_timeout
    assert server.posts == []  # 未发出任何 POST


async def test_remote_error_is_raised(monkeypatch):
    server = _FakeServer(error_methods={"tools/list"})
    _install(monkeypatch, server)

    with pytest.raises(BadRequestError, match="boom"):
        await sse.legacy_sse_json_rpc(SSE_URL, "tools/list", {}, timeout=5.0, connect_timeout=5.0)


# --- 外提后可直接单测的会话单元（改动前困在闭包里，无法覆盖）--------------------


def _session(*, timeout: float = 1.0) -> sse._LegacySseSession:
    return sse._LegacySseSession(
        sse_url=SSE_URL,
        get_headers={"Accept": "text/event-stream"},
        post_headers={"Content-Type": "application/json"},
        timeout=timeout,
    )


def test_handle_endpoint_rejects_cross_origin_and_leaves_session_unready():
    session = _session()
    with pytest.raises(BadRequestError, match="不同源"):
        session._handle_endpoint(SimpleNamespace(event="endpoint", data="https://evil.example.com/messages"))
    assert session.post_url is None
    assert not session.endpoint_ready.is_set()


def test_handle_endpoint_resolves_relative_url():
    session = _session()
    session._handle_endpoint(SimpleNamespace(event="endpoint", data="/messages?session=abc"))
    assert session.post_url == POST_URL
    assert session.endpoint_ready.is_set()


def test_handle_endpoint_skips_empty_data():
    session = _session()
    session._handle_endpoint(SimpleNamespace(event="endpoint", data=""))
    assert session.post_url is None
    assert not session.endpoint_ready.is_set()


async def test_handle_message_delivers_to_matching_future():
    session = _session()
    fut = asyncio.get_running_loop().create_future()
    session.pending[7] = fut
    session._handle_message(SimpleNamespace(data=json.dumps({"id": 7, "result": {"x": 1}})))
    assert fut.result()["result"] == {"x": 1}


async def test_handle_message_ignores_unrelated_or_non_int_id():
    session = _session()
    fut = asyncio.get_running_loop().create_future()
    session.pending[7] = fut
    session._handle_message(SimpleNamespace(data=json.dumps({"id": "7", "result": {}})))  # 字符串 id 不匹配
    session._handle_message(SimpleNamespace(data=json.dumps({"id": 42, "result": {}})))  # 未知 id
    session._handle_message(SimpleNamespace(data=""))  # keep-alive
    assert not fut.done()


async def test_read_events_wakes_pending_futures_on_stream_failure(monkeypatch):
    """读流中断必须唤醒等待方，否则 ``roundtrip`` 会一直挂到超时。"""
    session = _session()
    fut = asyncio.get_running_loop().create_future()
    session.pending[1] = fut

    class _ES:
        response = SimpleNamespace(raise_for_status=lambda: None)

        async def aiter_sse(self):
            raise RuntimeError("stream broken")
            yield  # pragma: no cover

    class _Ctx:
        async def __aenter__(self):
            return _ES()

        async def __aexit__(self, *args):  # noqa: ARG002
            return False

    monkeypatch.setattr(sse, "aconnect_sse", lambda *a, **kw: _Ctx())  # noqa: ARG005

    await session.read_events(object())  # type: ignore[arg-type]
    assert fut.done()
    with pytest.raises(RuntimeError, match="stream broken"):
        fut.result()


async def test_roundtrip_resolves_and_cleans_pending():
    session = _session()

    class _Client:
        async def post(self, url, json=None, headers=None):  # noqa: A002, ARG002
            rid = json["id"]
            session.pending[rid].set_result({"jsonrpc": "2.0", "id": rid, "result": {"ok": 1}})
            return _PostResp(200)

    out = await session.roundtrip(_Client(), POST_URL, "tools/list", {})
    assert out["result"] == {"ok": 1}
    assert session.pending == {}


async def test_roundtrip_raises_on_post_http_error():
    session = _session()

    class _Client:
        async def post(self, url, json=None, headers=None):  # noqa: A002, ARG002
            return _PostResp(500, "boom")

    with pytest.raises(BadRequestError, match="MCP POST 500"):
        await session.roundtrip(_Client(), POST_URL, "tools/list", {})

    # POST 失败也必须回收已登记的 Future，否则它会一直挂在 pending 上
    assert session.pending == {}


async def test_roundtrip_times_out_and_cleans_pending():
    session = _session(timeout=0.05)

    class _Client:
        async def post(self, url, json=None, headers=None):  # noqa: A002, ARG002
            return _PostResp(200)

    with pytest.raises(BadRequestError, match="响应超时") as ei:
        await session.roundtrip(_Client(), POST_URL, "tools/list", {})
    assert "tools/list" in str(ei.value)  # 报错须点明是哪个方法超时
    assert session.pending == {}
