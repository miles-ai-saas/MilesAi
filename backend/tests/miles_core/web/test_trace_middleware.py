"""TraceMiddleware 纯 ASGI：透传 / 生成 X-Trace-Id。"""

from __future__ import annotations

import pytest

from miles_common.trace import get_trace_id
from miles_core.web.middlewares.trace import TraceMiddleware


def _scope(*, trace_header: bytes | None = None) -> dict:
    headers = []
    if trace_header is not None:
        headers.append((b"x-trace-id", trace_header))
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/ping",
        "raw_path": b"/ping",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 1),
        "server": ("testserver", 80),
        "scheme": "http",
        "root_path": "",
    }


async def _ok_app(scope, receive, send):  # noqa: ANN001
    assert get_trace_id()
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


async def _empty_receive():
    return {"type": "http.disconnect"}


@pytest.mark.asyncio
async def test_trace_middleware_propagates_header():
    messages: list[dict] = []

    async def capture_send(message):  # noqa: ANN001
        messages.append(message)

    await TraceMiddleware(_ok_app)(_scope(trace_header=b"trace-fixed"), _empty_receive, capture_send)

    start = messages[0]
    assert start["status"] == 200
    headers = {k.decode().lower(): v.decode() for k, v in start["headers"]}
    assert headers["x-trace-id"] == "trace-fixed"
    assert get_trace_id() is None


@pytest.mark.asyncio
async def test_trace_middleware_generates_when_missing():
    messages: list[dict] = []

    async def capture_send(message):  # noqa: ANN001
        messages.append(message)

    await TraceMiddleware(_ok_app)(_scope(), _empty_receive, capture_send)

    headers = {k.decode().lower(): v.decode() for k, v in messages[0]["headers"]}
    assert headers["x-trace-id"]
    assert get_trace_id() is None
