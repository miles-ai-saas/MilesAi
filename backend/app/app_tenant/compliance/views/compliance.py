from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.common.schema import ApiResponse, PageParams, PageResult
from app.app_tenant.compliance.schemas.compliance import (
    InterceptLogOut,
    SensitiveWordCreate,
    SensitiveWordOut,
)
from app.app_tenant.compliance.services.compliance import ComplianceService

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> ComplianceService:
    return ComplianceService(db, ctx)


@router.get("/words", response_model=ApiResponse[PageResult[SensitiveWordOut]])
async def list_words(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("compliance:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_words(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/words", response_model=ApiResponse[SensitiveWordOut])
async def create_word(
    body: SensitiveWordCreate,
    ctx: TenantContext = Depends(require_permissions("compliance:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).create_word(body))


@router.delete("/words/{word_id}", response_model=ApiResponse[None])
async def delete_word(
    word_id: UUID,
    ctx: TenantContext = Depends(require_permissions("compliance:write")),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db, ctx).delete_word(word_id)
    return ok(message="已删除")


@router.get("/logs", response_model=ApiResponse[PageResult[InterceptLogOut]])
async def list_logs(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("compliance:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_logs(params)
    return page_ok(result.items, result.total, result.page, result.size)
