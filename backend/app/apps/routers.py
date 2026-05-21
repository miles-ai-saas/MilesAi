"""汇总租户端与运营端路由。"""

from app.admin.router import admin_router
from app.app_tenant.router import api_router

__all__ = ["api_router", "admin_router"]
