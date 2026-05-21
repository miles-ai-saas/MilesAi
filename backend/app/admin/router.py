from fastapi import APIRouter

from app.admin.app_ops.router import router as ops_router
from app.admin.app_sys.router import router as sys_router

admin_router = APIRouter(prefix="/api/admin/v1")
admin_router.include_router(sys_router)
admin_router.include_router(ops_router)
