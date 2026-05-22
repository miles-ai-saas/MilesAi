from fastapi import APIRouter

from app.admin.app_ops.views import audit, billing, model_catalog, risk, tenants

router = APIRouter(tags=["admin-ops"])
router.include_router(tenants.router)
router.include_router(billing.router)
router.include_router(risk.router)
router.include_router(audit.router)
router.include_router(model_catalog.router)
