from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.common.schema import ApiResponse, PageParams, PageResult
from app.app_tenant.system.schemas.user import UserCreate, UserOut, UserUpdate
from app.app_tenant.system.services.user import UserService

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
    ctx: TenantContext = Depends(require_permissions("system:user:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserOut]:
    return ok(await UserService(db, ctx).create_user(body))


@router.patch("/{user_id}", response_model=ApiResponse[UserOut])
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    ctx: TenantContext = Depends(require_permissions("system:user:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserOut]:
    return ok(await UserService(db, ctx).update_user(user_id, body))


@router.delete("/{user_id}", response_model=ApiResponse[UserOut])
async def deactivate_user(
    user_id: UUID,
    ctx: TenantContext = Depends(require_permissions("system:user:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserOut]:
    return ok(await UserService(db, ctx).deactivate_user(user_id))
