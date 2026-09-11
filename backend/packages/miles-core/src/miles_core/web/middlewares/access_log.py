"""HTTP 访问日志中间件（与 trace_id、统一 logging 配合）。"""

from __future__ import annotations

import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from miles_common.trace import get_trace_id
from miles_core.config import get_settings
from miles_core.logging import get_logger

logger = get_logger("app.http.access")

# 高频探测路径，避免刷屏
_DEFAULT_SKIP_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
)


def _should_skip(path: str) -> bool:
    if path in ("/favicon.ico",):
        return True
    if path.endswith("/health"):
        return True
    return any(path == prefix or path.startswith(prefix + "/") for prefix in _DEFAULT_SKIP_PREFIXES)


def _client_host(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "-"


class AccessLogMiddleware(BaseHTTPMiddleware):
    """记录 method、path、status、耗时、client、trace_id；不记录 Authorization / body。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """记录 method/path/status/耗时/client/trace_id；被跳过路径直接透传，异常记日志后原样抛出。"""
        settings = get_settings()
        if not settings.log_http_access:
            return await call_next(request)

        path = request.url.path
        if _should_skip(path):
            return await call_next(request)

        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            logger.exception(
                "request failed method=%s path=%s trace_id=%s",
                request.method,
                path,
                _resolve_trace_id(request),
            )
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            trace_id = _resolve_trace_id(request)
            query = request.url.query
            path_logged = f"{path}?{query}" if query and settings.debug else path
            logger.info(
                "%s %s %s %.1fms client=%s trace_id=%s",
                request.method,
                path_logged,
                status_code,
                duration_ms,
                _client_host(request),
                trace_id or "-",
            )


def _resolve_trace_id(request: Request) -> str | None:
    state_id = getattr(request.state, "trace_id", None)
    if state_id:
        return str(state_id)
    ctx_id = get_trace_id()
    return str(ctx_id) if ctx_id else None
