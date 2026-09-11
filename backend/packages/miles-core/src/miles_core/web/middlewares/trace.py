"""请求 trace_id 中间件：写入 request.state 与 ContextVar，响应头回传 X-Trace-Id。"""

from __future__ import annotations

import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from miles_common.trace import reset_trace_id, set_trace_id


def _attach_trace_id_to_span(trace_id: str) -> None:
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span.is_recording():
            span.set_attribute("miles.trace_id", trace_id)
    except ImportError:
        pass


class TraceMiddleware(BaseHTTPMiddleware):
    """为每个请求生成 / 透传 trace_id，写入 state 与 ContextVar，并在响应头回写 ``X-Trace-Id``。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """解析或生成 trace_id，注入 OTel span / request.state / ContextVar，响应结束后重置 ContextVar。"""
        trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
        request.state.trace_id = trace_id
        _attach_trace_id_to_span(trace_id)
        token = set_trace_id(trace_id)
        try:
            response = await call_next(request)
            response.headers["X-Trace-Id"] = trace_id
            return response
        finally:
            reset_trace_id(token)
