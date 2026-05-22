from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant.audit_log.repositories.audit_log import TenantAuditLogRepository
from app.tenant.audit_log.schemas.audit_log import TenantAuditLogOut
from app.common.schema import PageParams, PageResult
from app.core.tenant import TenantContext


async def write_tenant_audit_log(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    request: Request | None = None,
    detail: dict | None = None,
    user_id: UUID | None = None,
) -> None:
    ip = None
    ua = None
    if request:
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent")
    await TenantAuditLogRepository(db).create(
        tenant_id=ctx.tenant_id,
        user_id=user_id or ctx.user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip,
        user_agent=ua,
        detail=detail or {},
    )


class TenantAuditLogService:
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        self.db = db
        self.ctx = ctx
        self.repo = TenantAuditLogRepository(db)

    async def list_logs(
        self,
        params: PageParams,
        *,
        user_id: UUID | None = None,
        action: str | None = None,
    ) -> PageResult[TenantAuditLogOut]:
        page = await self.repo.list_by_tenant(
            self.ctx.tenant_id,
            page=params.page,
            size=params.size,
            user_id=user_id,
            action=action,
        )
        return PageResult(
            items=[TenantAuditLogOut.model_validate(r) for r in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )
