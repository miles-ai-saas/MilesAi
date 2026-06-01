"""服务线模板市场 HTTP API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.schemas.template_pack import (
    BizServiceLineTemplatePackApplyResult,
    BizServiceLineTemplatePackCreate,
    BizServiceLineTemplatePackOut,
    BizServiceLineTemplatePackUpdate,
)
from app.biz.services.template_pack_market import ServiceLineTemplatePackMarketService
from app.biz.services.template_pack_publish import ServiceLineTemplatePackPublishService
from app.common.response import ok
from app.common.schema import ApiResponse
from app.core.deps import require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db

router = APIRouter()


class TemplatePackCreateBody(BaseModel):
    service_line: str
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class TemplatePackUpdateBody(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    tags: list[str] | None = None


def _market_svc(db: AsyncSession, ctx: TenantContext) -> ServiceLineTemplatePackMarketService:
    return ServiceLineTemplatePackMarketService(db, ctx)


def _publish_svc(db: AsyncSession, ctx: TenantContext) -> ServiceLineTemplatePackPublishService:
    return ServiceLineTemplatePackPublishService(db, ctx)


@router.get("/mine", response_model=ApiResponse[list[BizServiceLineTemplatePackOut]])
async def list_my_template_packs(
    ctx: TenantContext = Depends(require_permissions("biz:project:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _publish_svc(db, ctx).list_mine())


@router.post("/mine", response_model=ApiResponse[BizServiceLineTemplatePackOut])
async def create_my_template_pack(
    body: TemplatePackCreateBody,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    payload = BizServiceLineTemplatePackCreate(
        service_line=body.service_line,
        name=body.name,
        description=body.description,
        tags=body.tags,
    )
    return ok(await _publish_svc(db, ctx).create_from_template(payload))


@router.patch("/mine/{pack_id}", response_model=ApiResponse[BizServiceLineTemplatePackOut])
async def update_my_template_pack(
    pack_id: UUID,
    body: TemplatePackUpdateBody,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    payload = BizServiceLineTemplatePackUpdate(name=body.name, description=body.description, tags=body.tags)
    return ok(await _publish_svc(db, ctx).update_mine(pack_id, payload))


@router.post("/mine/{pack_id}/submit", response_model=ApiResponse[BizServiceLineTemplatePackOut])
async def submit_my_template_pack(
    pack_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _publish_svc(db, ctx).submit(pack_id))


@router.delete("/mine/{pack_id}", response_model=ApiResponse[None])
async def withdraw_my_template_pack(
    pack_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    await _publish_svc(db, ctx).withdraw(pack_id)
    return ok(None)


@router.get("", response_model=ApiResponse[list[BizServiceLineTemplatePackOut]])
async def list_template_packs(
    service_line: str | None = Query(None),
    search: str | None = Query(None),
    featured: bool = Query(False),
    ctx: TenantContext = Depends(require_permissions("biz:project:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _market_svc(db, ctx).list_packs(service_line=service_line, search=search, featured_only=featured))


@router.get("/{pack_id}", response_model=ApiResponse[BizServiceLineTemplatePackOut])
async def get_template_pack(
    pack_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _market_svc(db, ctx).get_pack(pack_id))


@router.post("/{pack_id}/apply", response_model=ApiResponse[BizServiceLineTemplatePackApplyResult])
async def apply_template_pack(
    pack_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _market_svc(db, ctx).apply_pack(pack_id))
