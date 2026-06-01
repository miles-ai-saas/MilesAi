"""商机管理 HTTP API，路由前缀 `/biz/opportunities`。

提供商机的 CRUD 接口，支持按客户和阶段筛选；包含 POST /convert-to-project 转换端点，可将已赢单商机转为项目。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.schemas.opportunity import (
    BizOpportunityConvertOut,
    BizOpportunityCreate,
    BizOpportunityOut,
    BizOpportunityUpdate,
)
from app.biz.schemas.quote import BizQuoteCreate, BizQuoteOut, BizQuoteUpdate
from app.biz.services.opportunity import OpportunityService
from app.biz.services.quote import QuoteService
from app.common.response import ok, page_ok
from app.common.schema import ApiResponse, PageResult
from app.core.deps import require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> OpportunityService:
    return OpportunityService(db, ctx)


def _quote_svc(db: AsyncSession, ctx: TenantContext) -> QuoteService:
    return QuoteService(db, ctx)


@router.get("", response_model=ApiResponse[PageResult[BizOpportunityOut]])
async def list_opportunities(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    client_id: UUID | None = Query(None),
    stage: str | None = Query(None),
    ctx: TenantContext = Depends(require_permissions("biz:opportunity:read")),
    db: AsyncSession = Depends(get_db),
):
    """分页查询商机列表，支持按客户和阶段筛选。"""
    result = await _svc(db, ctx).list_opportunities(page=page, size=size, client_id=client_id, stage=stage)
    return page_ok(result.items, result.total, result.page, result.size)


@router.get("/pipeline", response_model=ApiResponse[list[BizOpportunityOut]])
async def list_opportunity_pipeline(
    ctx: TenantContext = Depends(require_permissions("biz:opportunity:read")),
    db: AsyncSession = Depends(get_db),
):
    """看板用：返回最近更新的商机列表（不分页）。"""
    return ok(await _svc(db, ctx).list_pipeline())


@router.post("", response_model=ApiResponse[BizOpportunityOut])
async def create_opportunity(
    body: BizOpportunityCreate,
    ctx: TenantContext = Depends(require_permissions("biz:opportunity:write")),
    db: AsyncSession = Depends(get_db),
):
    """创建新商机。"""
    return ok(await _svc(db, ctx).create(body))


@router.get("/{opportunity_id}", response_model=ApiResponse[BizOpportunityOut])
async def get_opportunity(
    opportunity_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:opportunity:read")),
    db: AsyncSession = Depends(get_db),
):
    """获取单个商机详情。"""
    return ok(await _svc(db, ctx).get(opportunity_id))


@router.patch("/{opportunity_id}", response_model=ApiResponse[BizOpportunityOut])
async def update_opportunity(
    opportunity_id: UUID,
    body: BizOpportunityUpdate,
    ctx: TenantContext = Depends(require_permissions("biz:opportunity:write")),
    db: AsyncSession = Depends(get_db),
):
    """更新商机信息。"""
    return ok(await _svc(db, ctx).update(opportunity_id, body))


@router.delete("/{opportunity_id}", response_model=ApiResponse[None])
async def delete_opportunity(
    opportunity_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:opportunity:write")),
    db: AsyncSession = Depends(get_db),
):
    """删除商机。"""
    await _svc(db, ctx).delete(opportunity_id)
    return ok(message="已删除")


@router.post("/{opportunity_id}/convert-to-project", response_model=ApiResponse[BizOpportunityConvertOut])
async def convert_to_project(
    opportunity_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:opportunity:write")),
    db: AsyncSession = Depends(get_db),
):
    """将赢单商机转为项目，并回写 converted_to_project_id。"""
    return ok(await _svc(db, ctx).convert_to_project(opportunity_id))


# ── quotes ──

@router.get("/{opportunity_id}/quotes", response_model=ApiResponse[list[BizQuoteOut]])
async def list_quotes(
    opportunity_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:opportunity:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _quote_svc(db, ctx).list_quotes(opportunity_id))


@router.post("/{opportunity_id}/quotes", response_model=ApiResponse[BizQuoteOut])
async def create_quote(
    opportunity_id: UUID,
    body: BizQuoteCreate,
    ctx: TenantContext = Depends(require_permissions("biz:opportunity:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _quote_svc(db, ctx).create(opportunity_id, body))


@router.patch("/{opportunity_id}/quotes/{quote_id}", response_model=ApiResponse[BizQuoteOut])
async def update_quote(
    opportunity_id: UUID,
    quote_id: UUID,
    body: BizQuoteUpdate,
    ctx: TenantContext = Depends(require_permissions("biz:opportunity:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _quote_svc(db, ctx).update(opportunity_id, quote_id, body))


@router.delete("/{opportunity_id}/quotes/{quote_id}", response_model=ApiResponse[None])
async def delete_quote(
    opportunity_id: UUID,
    quote_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:opportunity:write")),
    db: AsyncSession = Depends(get_db),
):
    await _quote_svc(db, ctx).delete(opportunity_id, quote_id)
    return ok(message="已删除")
