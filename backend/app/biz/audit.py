"""业务中心审计写入（复用租户 aud_logs）。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext
from app.tenant.audit_log.services.audit_log import write_tenant_audit_log


async def log_biz_action(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    action: str,
    resource_type: str,
    resource_id: UUID | str,
    detail: dict | None = None,
) -> None:
    await write_tenant_audit_log(
        db,
        ctx,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        detail=detail or {},
    )
