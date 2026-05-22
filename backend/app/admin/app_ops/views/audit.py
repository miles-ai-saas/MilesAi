from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_ops.services.audit import AdminAuditService
from app.admin.app_sys.deps import AdminContext, get_platform_admin
from app.common.response import page_ok
from app.common.schema import PageParams
from app.infra.db import get_db
from app.core.deps import get_page_params

router = APIRouter()


@router.get("/audit/logs")
async def audit_logs(
    params: PageParams = Depends(get_page_params),
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await AdminAuditService(db).list_audit_logs(params)
    return page_ok(result.items, result.total, result.page, result.size)
