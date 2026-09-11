"""对外 API 面（/api/v1/open/*）注册。路径保持不变，仅调整代码归属。"""

from __future__ import annotations

from fastapi import FastAPI

from miles_openapi.views import open_chat


def register_open(app: FastAPI) -> None:
    """挂载对外开放接口（X-API-Key 鉴权），不引入 admin 依赖。"""
    app.include_router(open_chat.router, prefix="/api/v1/open", tags=["open-agents"])
