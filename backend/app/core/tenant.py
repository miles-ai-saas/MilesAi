"""租户上下文与数据隔离工具。"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.sql.elements import ColumnElement

from app.common.exceptions import ForbiddenError


@dataclass(frozen=True)
class TenantContext:
    user_id: UUID
    tenant_id: UUID
    username: str
    is_superuser: bool
    permissions: frozenset[str]

    def has_permission(self, *codes: str) -> bool:
        if self.is_superuser:
            return True
        return all(c in self.permissions for c in codes)

    def require_permission(self, *codes: str) -> None:
        if not self.has_permission(*codes):
            missing = [c for c in codes if c not in self.permissions]
            raise ForbiddenError(f"缺少权限: {', '.join(missing)}")


def resolve_tenant_id(ctx: TenantContext, requested: UUID | None = None) -> UUID:
    """解析有效租户 ID：非超管只能使用自身租户。"""
    if requested is None:
        return ctx.tenant_id
    if not ctx.is_superuser and requested != ctx.tenant_id:
        raise ForbiddenError("无权访问其他租户")
    return requested


def assert_tenant_access(ctx: TenantContext, resource_tenant_id: UUID) -> None:
    """校验当前用户是否可访问目标租户资源。"""
    if ctx.is_superuser:
        return
    if resource_tenant_id != ctx.tenant_id:
        raise ForbiddenError("无权访问该租户资源")


def tenant_filters(
    ctx: TenantContext,
    tenant_column: ColumnElement,
    *,
    requested_tenant_id: UUID | None = None,
) -> list[ColumnElement[bool]]:
    """构建租户过滤条件，供分页/列表查询复用。"""
    if ctx.is_superuser:
        if requested_tenant_id is not None:
            return [tenant_column == requested_tenant_id]
        return []
    return [tenant_column == ctx.tenant_id]
