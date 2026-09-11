"""当前租户信息 HTTP API（超管可切换查看）。"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.infra.db import get_db
from miles_core.deps import get_page_params, require_permissions
from miles_common.response import ok, page_ok
from miles_core.tenant import TenantContext
from miles_common.schema import ApiResponse, PageParams, PageResult
from miles_portal.tenant.system.schemas.tenant import TenantCreate, TenantOut, TenantUpdate
from miles_portal.tenant.system.services.tenant import TenantService

router = APIRouter()


@router.get("", response_model=ApiResponse[PageResult[TenantOut]])
async def list_tenants(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("system:tenant:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[PageResult[TenantOut]]:
    svc = TenantService(db, ctx)
    result = await svc.list_tenants(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[TenantOut])
async def create_tenant(
    body: TenantCreate,
    ctx: TenantContext = Depends(require_permissions("system:tenant:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TenantOut]:
    return ok(await TenantService(db, ctx).create_tenant(body))


@router.get("/{tenant_id}", response_model=ApiResponse[TenantOut])
async def get_tenant(
    tenant_id: UUID,
    ctx: TenantContext = Depends(require_permissions("system:tenant:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TenantOut]:
    return ok(await TenantService(db, ctx).get_tenant(tenant_id))


@router.patch("/{tenant_id}", response_model=ApiResponse[TenantOut])
async def update_tenant(
    tenant_id: UUID,
    body: TenantUpdate,
    ctx: TenantContext = Depends(require_permissions("system:tenant:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TenantOut]:
    return ok(await TenantService(db, ctx).update_tenant(tenant_id, body))
