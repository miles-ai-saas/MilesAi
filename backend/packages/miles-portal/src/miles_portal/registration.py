"""租户域 API 注册：路由与域内依赖。"""

from __future__ import annotations

from fastapi import FastAPI

from miles_portal.tenant.router import api_router


def register_portal(app: FastAPI) -> None:
    """挂载租户端 API（/api/v1，前缀见 tenant.router）。"""
    app.include_router(api_router)
