from uuid import UUID

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import AuditLog
from app.core.repository import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, AuditLog)

    async def append(
        self,
        *,
        admin_id: UUID | None,
        action: str,
        tenant_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        request: Request | None = None,
        detail: dict | None = None,
    ) -> AuditLog:
        ip = None
        ua = None
        if request:
            ip = request.client.host if request.client else None
            ua = request.headers.get("user-agent")
        return await self.create(
            admin_id=admin_id,
            tenant_id=tenant_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip,
            user_agent=ua,
            detail=detail or {},
        )

    async def list_for_export(
        self,
        *,
        limit: int = 5000,
        admin_id: UUID | None = None,
        action: str | None = None,
        tenant_id: UUID | None = None,
    ) -> list[AuditLog]:
        filters = []
        if admin_id:
            filters.append(AuditLog.admin_id == admin_id)
        if action:
            filters.append(AuditLog.action == action)
        if tenant_id:
            filters.append(AuditLog.tenant_id == tenant_id)
        stmt = (
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .limit(max(1, min(limit, 5000)))
        )
        return list((await self.db.execute(stmt)).scalars().all())
