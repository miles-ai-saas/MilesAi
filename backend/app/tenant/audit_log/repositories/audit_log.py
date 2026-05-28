"""租户审计日志仓储。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant.audit_log.models import TenantAuditLog
from app.core.repository import BaseRepository


class TenantAuditLogRepository(BaseRepository[TenantAuditLog]):
    """append-only 风格；create 由 write_tenant_audit_log 调用。"""

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
        resource_type: str | None = None,
    ):
        filters = [TenantAuditLog.tenant_id == tenant_id]
        if user_id:
            filters.append(TenantAuditLog.user_id == user_id)
        if action:
            filters.append(TenantAuditLog.action == action)
        if resource_type:
            filters.append(TenantAuditLog.resource_type == resource_type)
        return await self.list_page(
            page=page,
            size=size,
            filters=filters,
            order_by=TenantAuditLog.created_at.desc(),
        )
