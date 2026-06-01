"""业务中心路由汇总，由 app.tenant.router 挂载 prefix="/biz"。

所有业务中心 API 共享 JWT 认证与 TenantContext，
权限码格式：biz:<资源>:<操作>（如 biz:project:read）
"""

from fastapi import APIRouter

from app.biz.views.client import router as client_router
from app.biz.views.contract import router as contract_router
from app.biz.views.dashboard import router as dashboard_router
from app.biz.views.deliverable import router as deliverable_router
from app.biz.views.export import router as export_router
from app.biz.views.service_line_template import router as service_line_template_router
from app.biz.views.meta import router as meta_router
from app.biz.views.opportunity import router as opportunity_router
from app.biz.views.milestone import router as milestone_router
from app.biz.views.payment import router as payment_router
from app.biz.views.project import router as project_router
from app.biz.views.supplier import router as supplier_router
from app.biz.views.work_package import router as work_package_router

biz_router = APIRouter()
biz_router.include_router(dashboard_router, prefix="/dashboard", tags=["business-dashboard"])
biz_router.include_router(meta_router, prefix="/meta", tags=["business-meta"])
biz_router.include_router(client_router, prefix="/clients", tags=["business-clients"])
biz_router.include_router(project_router, prefix="/projects", tags=["business-projects"])
biz_router.include_router(work_package_router, prefix="/work-packages", tags=["business-work-packages"])
biz_router.include_router(milestone_router, prefix="/milestones", tags=["business-milestones"])
biz_router.include_router(export_router, prefix="/export", tags=["business-export"])
biz_router.include_router(service_line_template_router, prefix="/service-line-templates", tags=["business-service-line-templates"])
biz_router.include_router(deliverable_router, prefix="/deliverables", tags=["business-deliverables"])
biz_router.include_router(opportunity_router, prefix="/opportunities", tags=["business-opportunities"])
biz_router.include_router(contract_router, prefix="/contracts", tags=["business-contracts"])
biz_router.include_router(supplier_router, prefix="/suppliers", tags=["business-suppliers"])
biz_router.include_router(payment_router, prefix="/payments", tags=["business-payments"])
