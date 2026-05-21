from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_ops.repositories.audit import AuditLogRepository
from app.admin.app_ops.schemas.audit import AuditLogOut
from app.admin.models import AuditLog
from app.common.schema import PageParams, PageResult


async def write_audit_log(
    db: AsyncSession,
    *,
    admin_id: UUID | None,
    action: str,
    tenant_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    request: Request | None = None,
    detail: dict | None = None,
) -> None:
    await AuditLogRepository(db).append(
        admin_id=admin_id,
        action=action,
        tenant_id=tenant_id,
        resource_type=resource_type,
        resource_id=resource_id,
        request=request,
        detail=detail,
    )


class AdminAuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = AuditLogRepository(db)

    async def list_audit_logs(self, params: PageParams) -> PageResult[AuditLogOut]:
        page = await self.repo.list_page(
            page=params.page,
            size=params.size,
            order_by=AuditLog.created_at.desc(),
        )
        return PageResult(
            items=[AuditLogOut.model_validate(r) for r in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )
