"""运营能力路由：租户、计费、风控、审计、模型目录（挂载于 /api/admin/v1）。"""

from fastapi import APIRouter

from app.admin.app_ops.views import audit, billing, model_catalog, risk, tenants

router = APIRouter(tags=["admin-ops"])
router.include_router(tenants.router)
router.include_router(billing.router)
router.include_router(risk.router)
router.include_router(audit.router)
router.include_router(model_catalog.router)
