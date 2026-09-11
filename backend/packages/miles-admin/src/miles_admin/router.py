"""运营后台 API（/api/admin/v1）：与租户 JWT 分离，见 app_sys / app_ops。"""

from fastapi import APIRouter

from miles_admin.app_ops.router import router as ops_router
from miles_admin.app_sys.router import router as sys_router

admin_router = APIRouter(prefix="/api/admin/v1")
admin_router.include_router(sys_router)
admin_router.include_router(ops_router)
