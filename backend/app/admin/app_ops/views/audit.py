"""运营端审计查询 API。"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_ops.services.audit import AdminAuditService
from app.admin.app_sys.deps import AdminContext, get_platform_admin, require_admin_role
from app.common.response import ok, page_ok
from app.common.schema import PageParams
from app.infra.db import get_db
from app.core.deps import get_page_params

router = APIRouter()


@router.get("/audit/meta")
async def audit_meta(
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return ok(await AdminAuditService(db).get_meta())


@router.get("/audit/logs")
async def audit_logs(
    admin_id: UUID | None = Query(None),
    action: str | None = Query(None),
    tenant_id: UUID | None = Query(None),
    created_from: date | None = Query(None, description="开始日期（含）"),
    created_to: date | None = Query(None, description="结束日期（含）"),
    params: PageParams = Depends(get_page_params),
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await AdminAuditService(db).list_audit_logs(
        params,
        admin_id=admin_id,
        action=action,
        tenant_id=tenant_id,
        created_from=created_from,
        created_to=created_to,
    )
    return page_ok(result.items, result.total, result.page, result.size)


