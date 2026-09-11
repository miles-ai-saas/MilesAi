"""开放面路由：与租户工作台同前缀 /api/v1，独立挂载以保持分层单向。

openapi 位于 portal 之上，故此处可以 import portal 的视图与依赖。
"""

from fastapi import APIRouter

from app.tenant.agents.views import open_chat as agents_open_chat

openapi_router = APIRouter(prefix="/api/v1")
openapi_router.include_router(agents_open_chat.router, prefix="/open", tags=["open-agents"])

__all__ = ["openapi_router"]
