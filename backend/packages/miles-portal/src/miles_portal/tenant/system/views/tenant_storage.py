"""租户 L2 对象存储 BYOK API。"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.response import ok
from miles_common.schema import ApiResponse
from miles_core.deps import require_permissions
from miles_core.infra.db import get_db
from miles_core.tenant import TenantContext
from miles_portal.tenant.system.schemas.tenant_storage import (
    TenantObjectStorageOut,
    TenantObjectStorageTestResult,
    TenantObjectStorageUpsert,
)
from miles_portal.tenant.system.services.tenant_storage import TenantObjectStorageService

router = APIRouter()


@router.get("", response_model=ApiResponse[TenantObjectStorageOut])
async def get_tenant_object_storage(
    ctx: TenantContext = Depends(require_permissions("system:config:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await TenantObjectStorageService(db, ctx).get_config())


@router.put("", response_model=ApiResponse[TenantObjectStorageOut])
async def upsert_tenant_object_storage(
    body: TenantObjectStorageUpsert,
    request: Request,
    ctx: TenantContext = Depends(require_permissions("system:config:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await TenantObjectStorageService(db, ctx).upsert_config(body, request=request))


@router.post("/test-connection", response_model=ApiResponse[TenantObjectStorageTestResult])
async def test_tenant_object_storage(
    body: TenantObjectStorageUpsert | None = None,
    ctx: TenantContext = Depends(require_permissions("system:config:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await TenantObjectStorageService(db, ctx).test_connection(body))
