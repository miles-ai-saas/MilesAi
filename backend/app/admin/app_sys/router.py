"""平台管理员认证路由（/api/admin/v1，与 app_ops 并列挂载）。"""

from fastapi import APIRouter

from app.admin.app_sys.views import auth

router = APIRouter()
router.include_router(auth.router)
