"""HTTP 中间件：在此实现，由 ``register_http_middlewares`` 统一挂载。

请求方向（外 → 内）：Trace → PlatformRisk → AccessLog → CORS → 路由
（Starlette 后注册的 ``add_middleware`` 更靠外层）
"""

from fastapi import FastAPI

from miles_core.web.middlewares.access_log import AccessLogMiddleware
from miles_core.web.middlewares.platform_risk import PlatformRiskMiddleware
from miles_core.web.middlewares.trace import TraceMiddleware

__all__ = [
    "AccessLogMiddleware",
    "PlatformRiskMiddleware",
    "TraceMiddleware",
    "register_http_middlewares",
]


def register_http_middlewares(app: FastAPI) -> None:
    """在 CORSMiddleware 之后调用，挂载访问日志、风控与 trace。"""
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(PlatformRiskMiddleware)
    app.add_middleware(TraceMiddleware)
