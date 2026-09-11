"""ASGI 入口：uvicorn miles_server.main:app。

路由与中间件在 apps.application.create_app；租户 API 前缀见 apps.routers.api_router。
"""

from miles_server.apps.application import create_app

app = create_app()
