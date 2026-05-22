from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.core.deps import get_tenant_context
from app.common.response import ok
from app.core.tenant import TenantContext
from app.tenant.auth.schemas.auth import LoginRequest, RefreshRequest, TokenResponse, UserInfo
from app.common.schema import ApiResponse
from app.tenant.auth.services.auth import AuthService

router = APIRouter()


def _auth_svc(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(
    body: LoginRequest,
    svc: AuthService = Depends(_auth_svc),
) -> ApiResponse[TokenResponse]:
    return ok(await svc.login(body))


@router.post("/logout", response_model=ApiResponse[None])
async def logout(
    ctx: TenantContext = Depends(get_tenant_context),
    svc: AuthService = Depends(_auth_svc),
) -> ApiResponse[None]:
    await svc.logout(ctx.user_id)
    return ok(message="已登出")


@router.get("/me", response_model=ApiResponse[UserInfo])
async def me(
    ctx: TenantContext = Depends(get_tenant_context),
    svc: AuthService = Depends(_auth_svc),
) -> ApiResponse[UserInfo]:
    return ok(await svc.get_me(ctx))


@router.post("/refresh", response_model=ApiResponse[TokenResponse])
async def refresh_token(
    body: RefreshRequest,
    svc: AuthService = Depends(_auth_svc),
) -> ApiResponse[TokenResponse]:
    return ok(await svc.refresh(body.refresh_token))
