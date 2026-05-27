"""运营端工作台分类（sys_categories）HTTP API。

前缀：``/api/admin/v1/sys-categories`` — 全平台全局字典，无租户副本与 provision。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_ops.schemas.sys_category import (
    SysCategoryAdminCreate,
    SysCategoryAdminOut,
    SysCategoryAdminUpdate,
)
from app.admin.app_ops.services.audit import write_audit_log
from app.admin.app_ops.services.sys_category import AdminSysCategoryService
from app.admin.app_sys.deps import AdminContext, get_platform_admin, require_admin_role
from app.common.response import ok
from app.common.schema import ApiResponse
from app.infra.db import get_db

router = APIRouter(prefix="/sys-categories")


@router.get("", response_model=ApiResponse[list[SysCategoryAdminOut]])
async def list_sys_categories(
    domain: str = Query(..., description="agent | prompt | skill | tool"),
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return ok(await AdminSysCategoryService(db).list_by_domain(domain))


@router.post("", response_model=ApiResponse[SysCategoryAdminOut])
async def create_sys_category(
    body: SysCategoryAdminCreate,
    domain: str = Query(...),
    request: Request = None,
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    row = await AdminSysCategoryService(db).create(domain, body)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="category.create",
        resource_type="sys_category",
        resource_id=str(row.id),
        request=request,
        detail={"domain": domain, "name": row.name},
    )
    return ok(row)


@router.patch("/{category_id}", response_model=ApiResponse[SysCategoryAdminOut])
async def update_sys_category(
    category_id: UUID,
    body: SysCategoryAdminUpdate,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    row = await AdminSysCategoryService(db).update(category_id, body)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="category.update",
        resource_type="sys_category",
        resource_id=str(category_id),
        request=request,
        detail=body.model_dump(mode="json", exclude_unset=True),
    )
    return ok(row)


@router.delete("/{category_id}", response_model=ApiResponse[None])
async def delete_sys_category(
    category_id: UUID,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    await AdminSysCategoryService(db).delete(category_id)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="category.delete",
        resource_type="sys_category",
        resource_id=str(category_id),
        request=request,
    )
    return ok(message="已删除")
