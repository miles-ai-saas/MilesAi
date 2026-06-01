"""商机管理 HTTP API，路由前缀 `/biz/opportunities`。

提供商机的 CRUD 接口，支持按客户和阶段筛选；包含 POST /convert-to-project 转换端点，可将已赢单商机转为项目。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.schemas.opportunity import (
    BizOpportunityCreate,
    BizOpportunityOut,
    BizOpportunityUpdate,
)
from app.biz.services.opportunity import OpportunityService
from app.common.response import ok, page_ok
from app.common.schema import ApiResponse, PageResult
from app.core.deps import require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> OpportunityService:
    return OpportunityService(db, ctx)


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


@router.post("/{opportunity_id}/convert-to-project", response_model=ApiResponse[BizOpportunityOut])
async def convert_to_project(
    opportunity_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:opportunity:write")),
    db: AsyncSession = Depends(get_db),
):
    """将已赢单商机转为项目——Phase 3 占位，后续实现完整转换逻辑。"""
    svc = _svc(db, ctx)
    opp = await svc.get(opportunity_id)
    if opp.stage not in ("won",):
        return ok(message="仅已赢单的商机可转为项目", data=opp)
    # 占位：更新商机状态
    await svc.update(opportunity_id, BizOpportunityUpdate(stage="won"))
    return ok(await svc.get(opportunity_id))
