from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_ops.services.audit import write_audit_log
from app.admin.app_ops.services.tenant import AdminTenantService
from app.admin.app_ops.schemas import AdminTenantCreate, AdminTenantUpdate, TenantQuotaUpdate
from app.admin.app_sys.deps import AdminContext, get_platform_admin
from app.common.response import ok, page_ok
from app.common.schema import PageParams
from app.core.database import get_db
from app.core.deps import get_page_params
from app.models.tenant import TenantStatus

router = APIRouter()


@router.get("/tenants")
async def list_tenants(
    status: TenantStatus | None = None,
    plan_id: UUID | None = None,
    is_active: bool | None = None,
    params: PageParams = Depends(get_page_params),
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await AdminTenantService(db).list_tenants(
        params, status=status, plan_id=plan_id, is_active=is_active
    )
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/tenants")
async def create_tenant(
    body: AdminTenantCreate,
    request: Request,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    tenant = await AdminTenantService(db).create_tenant(body)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="tenant.create",
        tenant_id=tenant.id,
        resource_type="tenant",
        resource_id=str(tenant.id),
        request=request,
        detail=body.model_dump(mode="json"),
    )
    return ok(tenant)


@router.get("/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: UUID,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return ok(await AdminTenantService(db).get_tenant_detail(tenant_id))


@router.patch("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: UUID,
    body: AdminTenantUpdate,
    request: Request,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    tenant = await AdminTenantService(db).update_tenant(tenant_id, body)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="tenant.update",
        tenant_id=tenant_id,
        resource_type="tenant",
        resource_id=str(tenant_id),
        request=request,
        detail=body.model_dump(mode="json", exclude_unset=True),
    )
    return ok(tenant)


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: UUID,
    request: Request,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    await AdminTenantService(db).delete_tenant(tenant_id)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="tenant.delete",
        tenant_id=tenant_id,
        resource_type="tenant",
        resource_id=str(tenant_id),
        request=request,
    )
    return ok(None)


@router.patch("/tenants/{tenant_id}/quota")
async def update_quota(
    tenant_id: UUID,
    body: TenantQuotaUpdate,
    request: Request,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    tenant = await AdminTenantService(db).update_quota(tenant_id, body)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="tenant.quota",
        tenant_id=tenant_id,
        request=request,
        detail=body.model_dump(mode="json", exclude_unset=True),
    )
    return ok(tenant)
