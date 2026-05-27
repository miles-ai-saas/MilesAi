"""运营端审计：管理员操作写库与分页查询。"""

import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_ops.repositories.audit import AuditLogRepository
from app.admin.app_ops.schemas.audit import AuditAdminOption, AuditLogOut, AuditMetaOut
from app.admin.models import AuditLog
from app.common.schema import PageParams, PageResult

EXPORT_MAX_ROWS = 5000


def _day_start(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


def _day_end_exclusive(d: date) -> datetime:
    return _day_start(d) + timedelta(days=1)


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
    """视图层在变更成功后调用，记录操作者与 Request 元数据。"""
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
    """运营审计日志只读列表。"""

    def __init__(self, db: AsyncSession) -> None:
        self.repo = AuditLogRepository(db)

    def _date_filters(
        self,
        *,
        created_from: date | None,
        created_to: date | None,
    ) -> list:
        filters = []
        if created_from:
            filters.append(AuditLog.created_at >= _day_start(created_from))
        if created_to:
            filters.append(AuditLog.created_at < _day_end_exclusive(created_to))
        return filters

    async def _hydrate_usernames(self, rows: list[AuditLog]) -> list[AuditLogOut]:
        admin_ids = {r.admin_id for r in rows if r.admin_id}
        names = await self.repo.load_admin_usernames(admin_ids)
        items: list[AuditLogOut] = []
        for row in rows:
            out = AuditLogOut.model_validate(row)
            items.append(
                out.model_copy(
                    update={"admin_username": names.get(row.admin_id) if row.admin_id else None}
                )
            )
        return items

    async def list_audit_logs(
        self,
        params: PageParams,
        *,
        admin_id: UUID | None = None,
        action: str | None = None,
        tenant_id: UUID | None = None,
        created_from: date | None = None,
        created_to: date | None = None,
    ) -> PageResult[AuditLogOut]:
        filters = []
        if admin_id:
            filters.append(AuditLog.admin_id == admin_id)
        if action:
            filters.append(AuditLog.action == action)
        if tenant_id:
            filters.append(AuditLog.tenant_id == tenant_id)
        filters.extend(self._date_filters(created_from=created_from, created_to=created_to))
        page = await self.repo.list_page(
            page=params.page,
            size=params.size,
            filters=filters or None,
            order_by=AuditLog.created_at.desc(),
        )
        items = await self._hydrate_usernames(page.items)
        return PageResult(
            items=items,
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def get_meta(self) -> AuditMetaOut:
        actions = await self.repo.list_distinct_actions()
        admins = await self.repo.list_audit_admins()
        return AuditMetaOut(
            actions=actions,
            admins=[AuditAdminOption(id=a.id, username=a.username) for a in admins],
        )

    async def export_logs_csv(
        self,
        *,
        admin_id: UUID | None = None,
        action: str | None = None,
        tenant_id: UUID | None = None,
        created_from: date | None = None,
        created_to: date | None = None,
        limit: int = EXPORT_MAX_ROWS,
    ) -> str:
        rows = await self.repo.list_for_export(
            limit=limit,
            admin_id=admin_id,
            action=action,
            tenant_id=tenant_id,
            created_from=created_from,
            created_to=created_to,
        )
        admin_ids = {r.admin_id for r in rows if r.admin_id}
        names = await self.repo.load_admin_usernames(admin_ids)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "created_at",
                "action",
                "admin_id",
                "admin_username",
                "tenant_id",
                "resource_type",
                "resource_id",
                "ip_address",
                "detail",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.created_at.isoformat() if row.created_at else "",
                    row.action,
                    str(row.admin_id) if row.admin_id else "",
                    names.get(row.admin_id, "") if row.admin_id else "",
                    str(row.tenant_id) if row.tenant_id else "",
                    row.resource_type or "",
                    row.resource_id or "",
                    row.ip_address or "",
                    str(row.detail or {}),
                ]
            )
        return buf.getvalue()
