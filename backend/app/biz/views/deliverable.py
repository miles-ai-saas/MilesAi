"""交付物管理 HTTP API，路由前缀 `/biz/deliverables`。

GET 列表需要 project_id 查询参数（必填）；POST/PATCH/DELETE 操作独立的交付物资源。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.schemas.deliverable import (
    BizDeliverableCreate,
    BizDeliverableOut,
    BizDeliverableUpdate,
)
from app.biz.services.deliverable import DeliverableService
from app.common.response import ok
from app.common.schema import ApiResponse
from app.core.deps import require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> DeliverableService:
    return DeliverableService(db, ctx)


@router.get("", response_model=ApiResponse[list[BizDeliverableOut]])
async def list_deliverables(
    project_id: UUID = Query(...),
    ctx: TenantContext = Depends(require_permissions("biz:project:read")),
    db: AsyncSession = Depends(get_db),
):
    """按项目查询交付物列表，project_id 必填。"""
    return ok(await _svc(db, ctx).list_by_project(project_id))


@router.post("", response_model=ApiResponse[BizDeliverableOut])
async def create_deliverable(
    body: BizDeliverableCreate,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    """创建交付物。"""
    return ok(await _svc(db, ctx).create(body))


@router.patch("/{deliverable_id}", response_model=ApiResponse[BizDeliverableOut])
async def update_deliverable(
    deliverable_id: UUID,
    body: BizDeliverableUpdate,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    """更新交付物信息。"""
    return ok(await _svc(db, ctx).update(deliverable_id, body))


@router.delete("/{deliverable_id}", response_model=ApiResponse[None])
async def delete_deliverable(
    deliverable_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:project:write")),
    db: AsyncSession = Depends(get_db),
):
    """删除交付物。"""
    await _svc(db, ctx).delete(deliverable_id)
    return ok(message="已删除")
