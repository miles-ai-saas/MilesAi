"""平台管理员治理 HTTP API（super_admin）。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from miles_admin.app_ops.schemas.admin import (
    AdminResetPasswordRequest,
    PlatformAdminCreate,
    PlatformAdminUpdate,
)
from miles_admin.app_ops.services.admins import AdminManagementService
from miles_admin.app_ops.services.audit import write_audit_log
from miles_admin.app_sys.deps import AdminContext, require_admin_role
from miles_common.response import ok, page_ok
from miles_common.schema import PageParams
from miles_core.deps import get_page_params
from miles_core.infra.db import get_db

router = APIRouter()


@router.get("/admins")
async def list_admins(
    params: PageParams = Depends(get_page_params),
    ctx: AdminContext = Depends(require_admin_role("super_admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await AdminManagementService(db).list_admins(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/admins")
async def create_admin(
    body: PlatformAdminCreate,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("super_admin")),
    db: AsyncSession = Depends(get_db),
):
    admin = await AdminManagementService(db).create_admin(body)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="admin.create",
        resource_type="admin",
        resource_id=str(admin.id),
        request=request,
        detail={"username": admin.username, "role": admin.role},
    )
    return ok(admin)


@router.patch("/admins/{admin_id}")
async def update_admin(
    admin_id: UUID,
    body: PlatformAdminUpdate,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("super_admin")),
    db: AsyncSession = Depends(get_db),
):
    admin = await AdminManagementService(db).update_admin(admin_id, body, actor_id=ctx.admin_id)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="admin.update",
        resource_type="admin",
        resource_id=str(admin_id),
        request=request,
        detail=body.model_dump(mode="json", exclude_unset=True),
    )
    return ok(admin)


@router.delete("/admins/{admin_id}")
async def disable_admin(
    admin_id: UUID,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("super_admin")),
    db: AsyncSession = Depends(get_db),
):
    await AdminManagementService(db).disable_admin(admin_id, actor_id=ctx.admin_id)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="admin.disable",
        resource_type="admin",
        resource_id=str(admin_id),
        request=request,
    )
    return ok(None)


@router.post("/admins/{admin_id}/reset-password")
async def reset_admin_password(
    admin_id: UUID,
    body: AdminResetPasswordRequest,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("super_admin")),
    db: AsyncSession = Depends(get_db),
):
    await AdminManagementService(db).reset_password(admin_id, body)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="admin.reset_password",
        resource_type="admin",
        resource_id=str(admin_id),
        request=request,
    )
    return ok(message="密码已重置，目标账号需重新登录")
