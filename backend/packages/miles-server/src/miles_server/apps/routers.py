"""汇总租户端（/api/v1）与运营端（/api/admin/v1）路由。"""

from miles_admin.router import admin_router
from miles_openapi.registration import openapi_router
from miles_portal.tenant.router import api_router

__all__ = ["api_router", "admin_router", "openapi_router"]
