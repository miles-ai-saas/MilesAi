"""对外 API 面（``/api/v1/open/*`` 与 A2A well-known）注册。路径保持不变，仅调整代码归属。"""

from __future__ import annotations

from fastapi import FastAPI

from miles_openapi.views import a2a_server, open_chat


def register_open(app: FastAPI) -> None:
    """挂载对外开放接口（X-API-Key 鉴权），不引入 admin 依赖。

    A2A 的 Card 发现端点为公开元数据（无鉴权），故 root 路由器不加 ``/api/v1/open``
    前缀 —— ``/.well-known/agent-card.json`` 是协议约定的固定路径。
    """
    app.include_router(open_chat.router, prefix="/api/v1/open", tags=["open-agents"])
    app.include_router(a2a_server.router, prefix="/api/v1/open", tags=["open-a2a"])
    app.include_router(a2a_server.well_known_router, tags=["open-a2a"])
