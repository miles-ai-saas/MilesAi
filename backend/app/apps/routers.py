"""汇总租户端（/api/v1）与运营端（/api/admin/v1）路由。"""

from app.admin.router import admin_router
from app.openapi.registration import openapi_router
from app.tenant.router import api_router

__all__ = ["api_router", "admin_router", "openapi_router"]
