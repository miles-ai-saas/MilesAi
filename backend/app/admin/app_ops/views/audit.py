"""运营端审计查询 API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_ops.services.audit import AdminAuditService
from app.admin.app_sys.deps import AdminContext, get_platform_admin, require_admin_role
from app.common.response import page_ok
from app.common.schema import PageParams
from app.infra.db import get_db
from app.core.deps import get_page_params

router = APIRouter()


@router.get("/audit/logs")
async def audit_logs(
    admin_id: UUID | None = Query(None),
    action: str | None = Query(None),
    tenant_id: UUID | None = Query(None),
    params: PageParams = Depends(get_page_params),
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await AdminAuditService(db).list_audit_logs(
        params,
        admin_id=admin_id,
        action=action,
        tenant_id=tenant_id,
    )
    return page_ok(result.items, result.total, result.page, result.size)


@router.get("/audit/logs/export")
async def export_audit_logs(
    admin_id: UUID | None = Query(None),
    action: str | None = Query(None),
    tenant_id: UUID | None = Query(None),
    limit: int = Query(5000, ge=1, le=5000),
    ctx: AdminContext = Depends(require_admin_role("security")),
    db: AsyncSession = Depends(get_db),
):
    csv_text = await AdminAuditService(db).export_logs_csv(
        admin_id=admin_id,
        action=action,
        tenant_id=tenant_id,
        limit=limit,
    )
    return PlainTextResponse(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="admin-audit-logs.csv"'},
    )
