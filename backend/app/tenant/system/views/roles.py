"""角色与权限 HTTP API。"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.common.schema import ApiResponse, PageParams, PageResult
from app.tenant.system.schemas.role import (
    PermissionGroupOut,
    RoleCreate,
    RoleOut,
    RoleUpdate,
)
from app.tenant.system.services.role import RoleService

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> RoleService:
    return RoleService(db, ctx)


@router.get("/permissions", response_model=ApiResponse[list[PermissionGroupOut]])
async def list_permissions(
    ctx: TenantContext = Depends(require_permissions("system:role:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).list_permissions())


@router.get("/assignable", response_model=ApiResponse[list[RoleOut]])
async def list_assignable_roles(
    ctx: TenantContext = Depends(require_permissions("system:role:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).list_assignable_roles())


@router.get("", response_model=ApiResponse[PageResult[RoleOut]])
async def list_roles(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("system:role:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_roles(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[RoleOut])
async def create_role(
    body: RoleCreate,
    ctx: TenantContext = Depends(require_permissions("system:role:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).create_role(body))


@router.patch("/{role_id}", response_model=ApiResponse[RoleOut])
async def update_role(
    role_id: UUID,
    body: RoleUpdate,
    ctx: TenantContext = Depends(require_permissions("system:role:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).update_role(role_id, body))


@router.delete("/{role_id}", response_model=ApiResponse[None])
async def delete_role(
    role_id: UUID,
    ctx: TenantContext = Depends(require_permissions("system:role:write")),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db, ctx).delete_role(role_id)
    return ok(message="已删除")
