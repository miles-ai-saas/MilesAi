"""服务线模板市场 HTTP API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.schemas.template_pack import BizServiceLineTemplatePackApplyResult, BizServiceLineTemplatePackOut
from app.biz.services.template_pack_market import ServiceLineTemplatePackMarketService
from app.common.response import ok
from app.common.schema import ApiResponse
from app.core.deps import require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> ServiceLineTemplatePackMarketService:
    return ServiceLineTemplatePackMarketService(db, ctx)


@router.get("", response_model=ApiResponse[list[BizServiceLineTemplatePackOut]])
async def list_template_packs(
    service_line: str | None = Query(None),
    search: str | None = Query(None),
    featured: bool = Query(False),
    ctx: TenantContext = Depends(require_permissions("biz:project:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).list_packs(service_line=service_line, search=search, featured_only=featured))


@router.get("/{pack_id}", response_model=ApiResponse[BizServiceLineTemplatePackOut])
async def get_template_pack(
    pack_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_pack(pack_id))


@router.post("/{pack_id}/apply", response_model=ApiResponse[BizServiceLineTemplatePackApplyResult])
async def apply_template_pack(
    pack_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).apply_pack(pack_id))
