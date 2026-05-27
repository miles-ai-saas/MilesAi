"""运营端审计：管理员操作写库与分页查询。"""

import csv
import io
from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_ops.repositories.audit import AuditLogRepository
from app.admin.app_ops.schemas.audit import AuditLogOut
from app.admin.models import AuditLog
from app.common.schema import PageParams, PageResult

EXPORT_MAX_ROWS = 5000


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

    async def list_audit_logs(
        self,
        params: PageParams,
        *,
        admin_id: UUID | None = None,
        action: str | None = None,
        tenant_id: UUID | None = None,
    ) -> PageResult[AuditLogOut]:
        filters = []
        if admin_id:
            filters.append(AuditLog.admin_id == admin_id)
        if action:
            filters.append(AuditLog.action == action)
        if tenant_id:
            filters.append(AuditLog.tenant_id == tenant_id)
        page = await self.repo.list_page(
            page=params.page,
            size=params.size,
            filters=filters or None,
            order_by=AuditLog.created_at.desc(),
        )
        return PageResult(
            items=[AuditLogOut.model_validate(r) for r in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def export_logs_csv(
        self,
        *,
        admin_id: UUID | None = None,
        action: str | None = None,
        tenant_id: UUID | None = None,
        limit: int = EXPORT_MAX_ROWS,
    ) -> str:
        rows = await self.repo.list_for_export(
            limit=limit,
            admin_id=admin_id,
            action=action,
            tenant_id=tenant_id,
        )
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "created_at",
                "action",
                "admin_id",
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
                    str(row.tenant_id) if row.tenant_id else "",
                    row.resource_type or "",
                    row.resource_id or "",
                    row.ip_address or "",
                    str(row.detail or {}),
                ]
            )
        return buf.getvalue()
