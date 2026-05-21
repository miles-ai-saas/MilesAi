from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.app_tenant.audit_log.models import TenantAuditLog
from app.core.repository import BaseRepository


class TenantAuditLogRepository(BaseRepository[TenantAuditLog]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, TenantAuditLog)

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        page: int = 1,
        size: int = 20,
        user_id: UUID | None = None,
        action: str | None = None,
    ):
        filters = [TenantAuditLog.tenant_id == tenant_id]
        if user_id:
            filters.append(TenantAuditLog.user_id == user_id)
        if action:
            filters.append(TenantAuditLog.action == action)
        return await self.list_page(
            page=page,
            size=size,
            filters=filters,
            order_by=TenantAuditLog.created_at.desc(),
        )
