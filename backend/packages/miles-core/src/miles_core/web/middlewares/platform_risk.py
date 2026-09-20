"""平台风控中间件：IP 黑名单与租户 API 限流。"""

from __future__ import annotations

from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from miles_common.trace import get_trace_id
from miles_core.models.risk import RateLimitScope, RiskSeverity
from miles_core.risk.enforce import platform_risk_enforcer

_SKIP_PREFIXES = ("/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico")

#: 超限对端可见文案。模块级单一来源：平台中间件的 IP 维度 429 与 A2A 端点的 Key 维度 429
#: 用的是同一句话，两处各写一份必然会漂移。
RATE_LIMIT_MESSAGE = "请求过于频繁，请稍后再试"


def client_ip(request: Request) -> str:
    """请求来源 IP：优先 ``X-Forwarded-For`` 首段（经代理时 ``request.client`` 是代理地址）。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _should_skip(path: str) -> bool:
    if path.endswith("/health"):
        return True
    return any(path == p or path.startswith(p + "/") for p in _SKIP_PREFIXES)


class PlatformRiskMiddleware(BaseHTTPMiddleware):
    """进入路由前拦截黑名单 IP，并对 ``/api/v1`` 做租户限流，命中即返回 403 / 429。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """执行 IP 封禁与限流检查；命中时记录风控事件并直接返回统一信封的 JSON 响应。"""
        path = request.url.path
        if _should_skip(path):
            return await call_next(request)

        ip = client_ip(request)

        if await platform_risk_enforcer.is_ip_blocked(ip):
            await platform_risk_enforcer.record_event(
                event_type="ip_blocked",
                severity=RiskSeverity.HIGH,
                ip_address=ip,
                detail={"kind": "ip_blocked", "path": path, "ip": ip},
            )
            return JSONResponse(
                status_code=403,
                content={
                    "code": 403,
                    "message": "访问被拒绝",
                    "data": None,
                    "trace_id": get_trace_id(),
                },
            )

        if path.startswith("/api/v1"):
            hit = await platform_risk_enforcer.check_rate_limit(path, ip, scope=RateLimitScope.IP)
            if hit:
                await platform_risk_enforcer.record_event(
                    event_type="rate_limit",
                    severity=RiskSeverity.MEDIUM,
                    ip_address=ip,
                    detail={
                        "kind": "rate_limit",
                        "path": path,
                        "ip": ip,
                        "rule_id": str(hit.rule_id),
                    },
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "code": 429,
                        "message": RATE_LIMIT_MESSAGE,
                        "data": None,
                        "trace_id": get_trace_id(),
                    },
                )

        return await call_next(request)
