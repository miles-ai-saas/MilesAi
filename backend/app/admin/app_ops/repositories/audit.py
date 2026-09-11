"""运营端审计日志仓储：写入与查询。"""

from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import Request
from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import AuditLog, PlatformAdmin
from app.core.repository import BaseRepository


def _day_start(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


def _day_end_exclusive(d: date) -> datetime:
    return _day_start(d) + timedelta(days=1)


class AuditLogRepository(BaseRepository[AuditLog]):
    """审计日志读写仓储。"""

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
        """新增一条审计记录；传入 Request 时自动提取客户端 IP 与 User-Agent。"""
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

    def _build_filters(
        self,
        *,
        admin_id: UUID | None = None,
        action: str | None = None,
        tenant_id: UUID | None = None,
        created_from: date | None = None,
        created_to: date | None = None,
    ) -> list:
        filters = []
        if admin_id:
            filters.append(AuditLog.admin_id == admin_id)
        if action:
            filters.append(AuditLog.action == action)
        if tenant_id:
            filters.append(AuditLog.tenant_id == tenant_id)
        if created_from:
            filters.append(AuditLog.created_at >= _day_start(created_from))
        if created_to:
            filters.append(AuditLog.created_at < _day_end_exclusive(created_to))
        return filters

    async def list_distinct_actions(self) -> list[str]:
        """返回已出现过的 action 去重列表（按字典序升序）。"""
        stmt = select(distinct(AuditLog.action)).order_by(AuditLog.action)
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_audit_admins(self) -> list[PlatformAdmin]:
        """返回产生过审计记录的管理员（按用户名升序）。"""
        stmt = select(PlatformAdmin).join(AuditLog, AuditLog.admin_id == PlatformAdmin.id).distinct().order_by(PlatformAdmin.username)
        return list((await self.db.execute(stmt)).scalars().all())

    async def load_admin_usernames(self, admin_ids: set[UUID]) -> dict[UUID, str]:
        """按 admin_id 批量查询用户名映射，供列表补全展示。"""
        if not admin_ids:
            return {}
        stmt = select(PlatformAdmin.id, PlatformAdmin.username).where(PlatformAdmin.id.in_(admin_ids))
        rows = (await self.db.execute(stmt)).all()
        return {row[0]: row[1] for row in rows}
