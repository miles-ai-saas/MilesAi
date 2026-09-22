"""请求 trace_id 中间件：写入 request.state 与 ContextVar，响应头回传 X-Trace-Id。"""

from __future__ import annotations

import uuid

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from miles_common.trace import reset_trace_id, set_trace_id


def _attach_trace_id_to_span(trace_id: str) -> None:
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span.is_recording():
            span.set_attribute("miles.trace_id", trace_id)
    except ImportError:
        # 静默可接受：opentelemetry 是可选依赖；未安装即不做 span 标注。
        pass


def _header_value(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers") or ():
        if key.lower() == name:
            return value.decode("latin-1")
    return None


class TraceMiddleware:
    """为每个请求生成 / 透传 trace_id，写入 state 与 ContextVar，并在响应头回写 ``X-Trace-Id``。"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        trace_id = _header_value(scope, b"x-trace-id") or str(uuid.uuid4())
        request = Request(scope, receive)
        request.state.trace_id = trace_id
        _attach_trace_id_to_span(trace_id)
        token = set_trace_id(trace_id)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(raw=list(message.get("headers") or []))
                headers["X-Trace-Id"] = trace_id
                message = {**message, "headers": headers.raw}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            reset_trace_id(token)
