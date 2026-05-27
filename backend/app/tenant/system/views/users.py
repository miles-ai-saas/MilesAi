"""租户用户管理 HTTP API（RBAC 用户，非平台管理员）。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.common.schema import ApiResponse, PageParams, PageResult
from app.tenant.system.schemas.user import UserBatchDeactivate, UserCreate, UserOut, UserResetPassword, UserUpdate
from app.tenant.system.services.user import UserService
from app.tenant.auth.schemas.auth import UserSessionOut
from app.tenant.auth.services.auth import AuthService

router = APIRouter()


@router.get("", response_model=ApiResponse[PageResult[UserOut]])
async def list_users(
    params: PageParams = Depends(get_page_params),
    tenant_id: UUID | None = None,
    ctx: TenantContext = Depends(require_permissions("system:user:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[PageResult[UserOut]]:
    result = await UserService(db, ctx).list_users(params, tenant_id=tenant_id)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[UserOut])
async def create_user(
    body: UserCreate,
    request: Request,
    ctx: TenantContext = Depends(require_permissions("system:user:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserOut]:
    return ok(await UserService(db, ctx).create_user(body, request=request))


@router.post("/batch-deactivate", response_model=ApiResponse[dict])
async def batch_deactivate_users(
    body: UserBatchDeactivate,
    request: Request,
    ctx: TenantContext = Depends(require_permissions("system:user:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    return ok(await UserService(db, ctx).batch_deactivate(body.user_ids, request=request))


@router.patch("/{user_id}", response_model=ApiResponse[UserOut])
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    request: Request,
    ctx: TenantContext = Depends(require_permissions("system:user:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserOut]:
    return ok(await UserService(db, ctx).update_user(user_id, body, request=request))


@router.post("/{user_id}/reset-password", response_model=ApiResponse[UserOut])
async def reset_user_password(
    user_id: UUID,
    body: UserResetPassword,
    request: Request,
    ctx: TenantContext = Depends(require_permissions("system:user:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserOut]:
    return ok(
        await UserService(db, ctx).reset_password(
            user_id, body.password, request=request
        )
    )


@router.delete("/{user_id}", response_model=ApiResponse[UserOut])
async def deactivate_user(
    user_id: UUID,
    request: Request,
    ctx: TenantContext = Depends(require_permissions("system:user:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserOut]:
    return ok(await UserService(db, ctx).deactivate_user(user_id, request=request))


@router.get("/{user_id}/sessions", response_model=ApiResponse[list[UserSessionOut]])
async def list_user_sessions(
    user_id: UUID,
    ctx: TenantContext = Depends(require_permissions("system:session:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[UserSessionOut]]:
    await UserService(db, ctx).get_user_or_raise(user_id)
    return ok(await AuthService(db, ctx).list_sessions(user_id))


@router.delete("/{user_id}/sessions", response_model=ApiResponse[dict])
async def revoke_all_user_sessions(
    user_id: UUID,
    ctx: TenantContext = Depends(require_permissions("system:session:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    await UserService(db, ctx).get_user_or_raise(user_id)
    n = await AuthService(db, ctx).admin_revoke_user_sessions(user_id)
    return ok({"revoked": n})
