"""平台管理员登录与会话 HTTP API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from miles_admin.app_ops.services.audit import write_audit_log
from miles_admin.app_sys.deps import AdminContext, get_platform_admin
from miles_admin.app_sys.schemas.auth import (
    AdminLoginRequest,
    AdminTokenResponse,
    PasswordChangeRequest,
)
from miles_admin.app_sys.services.auth import AdminAuthService
from miles_common.exceptions import ForbiddenError
from miles_common.response import ok
from miles_common.schema import ApiResponse
from miles_core.infra.db import get_db

router = APIRouter(prefix="/auth", tags=["admin-auth"])


@router.post("/login", response_model=ApiResponse[AdminTokenResponse])
async def admin_login(body: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    return ok(await AdminAuthService(db).login(body))


@router.post("/logout", response_model=ApiResponse[None])
async def admin_logout(
    request: Request,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    await AdminAuthService(db).logout(ctx.admin_id)
    await write_audit_log(db, admin_id=ctx.admin_id, action="admin.logout", request=request)
    return ok(message="已登出")


@router.get("/me")
async def admin_me(ctx: AdminContext = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)):
    return ok(await AdminAuthService(db).get_me(ctx.admin_id))


@router.post("/change-password", response_model=ApiResponse[None])
async def change_password(
    body: PasswordChangeRequest,
    request: Request,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    await AdminAuthService(db).change_password(ctx.admin_id, body)
    await write_audit_log(db, admin_id=ctx.admin_id, action="admin.change_password", request=request)
    return ok(message="密码已更新，请重新登录")


@router.get("/sessions")
async def list_sessions(
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return ok(await AdminAuthService(db).list_sessions(current_admin_id=ctx.admin_id))


@router.delete("/sessions/{admin_id}", response_model=ApiResponse[None])
async def revoke_session(
    admin_id: UUID,
    request: Request,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    if admin_id != ctx.admin_id and ctx.role != "super_admin":
        raise ForbiddenError("仅超级管理员可下线其他管理员会话")
    await AdminAuthService(db).revoke_session(admin_id)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="admin.revoke_session",
        request=request,
        detail={"target_admin_id": str(admin_id)},
    )
    return ok(message="会话已吊销")
