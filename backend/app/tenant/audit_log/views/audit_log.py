from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import page_ok
from app.core.tenant import TenantContext
from app.common.schema import ApiResponse, PageParams, PageResult
from app.tenant.audit_log.schemas.audit_log import TenantAuditLogOut
from app.tenant.audit_log.services.audit_log import TenantAuditLogService

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> TenantAuditLogService:
    return TenantAuditLogService(db, ctx)


@router.get("/logs", response_model=ApiResponse[PageResult[TenantAuditLogOut]])
async def list_audit_logs(
    params: PageParams = Depends(get_page_params),
    user_id: UUID | None = Query(None),
    action: str | None = Query(None),
    ctx: TenantContext = Depends(require_permissions("audit:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_logs(params, user_id=user_id, action=action)
    return page_ok(result.items, result.total, result.page, result.size)
