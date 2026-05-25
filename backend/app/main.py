"""ASGI 入口：uvicorn app.main:app。

路由与中间件在 apps.application.create_app；租户 API 前缀见 apps.routers.api_router。
"""

from app.apps.application import create_app

app = create_app()
