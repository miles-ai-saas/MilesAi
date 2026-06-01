"""租户操作审计写库与分页查询（与运营端 admin 审计分离）。"""

from uuid import UUID

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant.audit_log.meta import audit_meta_dict
from app.tenant.audit_log.repositories.audit_log import TenantAuditLogRepository
from app.tenant.audit_log.schemas.audit_log import TenantAuditLogOut
from app.tenant.audit_log.schemas.meta import AuditMetaOut
from app.common.schema import PageParams, PageResult
from app.core.tenant import TenantContext
from app.models.platform.user import User


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
    """业务变更成功后异步写入；不 commit（由调用方会话收尾）。"""
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


async def write_auth_login_audit(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """登录成功后写入审计（无 TenantContext）。"""
    await TenantAuditLogRepository(db).create(
        tenant_id=tenant_id,
        user_id=user_id,
        action="auth.login",
        resource_type="user",
        resource_id=str(user_id),
        ip_address=ip,
        user_agent=(user_agent or "")[:512] or None,
        detail={},
    )


class TenantAuditLogService:
    """租户内操作审计只读列表（写入用 write_tenant_audit_log）。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        self.db = db
        self.ctx = ctx
        self.repo = TenantAuditLogRepository(db)

    async def get_meta(self) -> AuditMetaOut:
        """返回枚举展示字典（无 DB 查询，文案来自 tenant/*/meta.py）。"""
        return AuditMetaOut.model_validate(audit_meta_dict())

    async def list_logs(
        self,
        params: PageParams,
        *,
        user_id: UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
    ) -> PageResult[TenantAuditLogOut]:
        page = await self.repo.list_by_tenant(
            self.ctx.tenant_id,
            page=params.page,
            size=params.size,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
        )
        user_ids = {row.user_id for row in page.items if row.user_id}
        username_by_id: dict[UUID, str] = {}
        if user_ids:
            result = await self.db.execute(select(User.id, User.username).where(User.id.in_(user_ids)))
            username_by_id = {uid: name for uid, name in result.all()}

        items: list[TenantAuditLogOut] = []
        for row in page.items:
            out = TenantAuditLogOut.model_validate(row)
            if row.user_id:
                out.username = username_by_id.get(row.user_id)
            items.append(out)
        return PageResult(
            items=items,
            total=page.total,
            page=page.page,
            size=page.size,
        )
