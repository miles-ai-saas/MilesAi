"""租户认证 HTTP API：登录、刷新、登出与当前用户信息。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.core.deps import bearer_scheme, get_tenant_context, require_permissions
from app.common.response import ok
from app.core.tenant import TenantContext
from app.tenant.auth.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserInfo,
    UserSessionOut,
)
from app.common.schema import ApiResponse
from app.tenant.auth.services.auth import AuthService

router = APIRouter()


def _auth_svc(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ua = request.headers.get("user-agent")
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)
    return ua, ip


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(
    body: LoginRequest,
    request: Request,
    svc: AuthService = Depends(_auth_svc),
) -> ApiResponse[TokenResponse]:
    ua, ip = _client_meta(request)
    return ok(await svc.login(body, user_agent=ua, ip=ip))


@router.post("/logout", response_model=ApiResponse[None])
async def logout(
    ctx: TenantContext = Depends(get_tenant_context),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    svc: AuthService = Depends(_auth_svc),
) -> ApiResponse[None]:
    token = credentials.credentials if credentials else None
    await svc.logout(ctx.user_id, access_token=token, current_jti=ctx.token_jti)
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
    request: Request,
    svc: AuthService = Depends(_auth_svc),
) -> ApiResponse[TokenResponse]:
    ua, ip = _client_meta(request)
    return ok(await svc.refresh(body.refresh_token, user_agent=ua, ip=ip))


@router.get("/sessions", response_model=ApiResponse[list[UserSessionOut]])
async def list_my_sessions(
    ctx: TenantContext = Depends(get_tenant_context),
    svc: AuthService = Depends(_auth_svc),
) -> ApiResponse[list[UserSessionOut]]:
    return ok(await svc.list_sessions(ctx.user_id, current_jti=ctx.token_jti))


@router.delete("/sessions/{jti}", response_model=ApiResponse[None])
async def revoke_my_session(
    jti: str,
    ctx: TenantContext = Depends(get_tenant_context),
    svc: AuthService = Depends(_auth_svc),
) -> ApiResponse[None]:
    await svc.revoke_session(ctx.user_id, jti, current_jti=ctx.token_jti)
    return ok(message="已强制下线该设备")


@router.post("/sessions/revoke-others", response_model=ApiResponse[dict])
async def revoke_other_sessions(
    ctx: TenantContext = Depends(get_tenant_context),
    svc: AuthService = Depends(_auth_svc),
) -> ApiResponse[dict]:
    n = await svc.revoke_other_sessions(ctx.user_id, keep_jti=ctx.token_jti)
    return ok({"revoked": n})
