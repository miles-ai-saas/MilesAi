from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.common.schema import ApiResponse, PageParams, PageResult
from app.app_tenant.flows.schemas.flow import (
    FlowCreate,
    FlowOut,
    FlowRunRequest,
    FlowRunResponse,
    FlowSaveGraph,
    FlowUpdate,
    FlowVersionOut,
)
from app.app_tenant.flows.services.flow import FlowService

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> FlowService:
    return FlowService(db, ctx)


@router.get("", response_model=ApiResponse[PageResult[FlowOut]])
async def list_flows(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("flow:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_flows(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[FlowOut])
async def create_flow(
    body: FlowCreate,
    ctx: TenantContext = Depends(require_permissions("flow:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).create_flow(body))


@router.get("/{flow_id}", response_model=ApiResponse[FlowOut])
async def get_flow(
    flow_id: UUID,
    ctx: TenantContext = Depends(require_permissions("flow:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_flow(flow_id))


@router.patch("/{flow_id}", response_model=ApiResponse[FlowOut])
async def update_flow(
    flow_id: UUID,
    body: FlowUpdate,
    ctx: TenantContext = Depends(require_permissions("flow:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).update_flow(flow_id, body))


@router.put("/{flow_id}/graph", response_model=ApiResponse[FlowVersionOut])
async def save_graph(
    flow_id: UUID,
    body: FlowSaveGraph,
    ctx: TenantContext = Depends(require_permissions("flow:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).save_graph(flow_id, body))


@router.get("/{flow_id}/graph", response_model=ApiResponse[FlowVersionOut])
async def get_graph(
    flow_id: UUID,
    ctx: TenantContext = Depends(require_permissions("flow:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_current_graph(flow_id))


@router.delete("/{flow_id}", response_model=ApiResponse[None])
async def delete_flow(
    flow_id: UUID,
    ctx: TenantContext = Depends(require_permissions("flow:write")),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db, ctx).delete_flow(flow_id)
    return ok(message="流程已删除")


@router.post("/{flow_id}/publish", response_model=ApiResponse[FlowOut])
async def publish_flow(
    flow_id: UUID,
    ctx: TenantContext = Depends(require_permissions("flow:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).publish(flow_id))


@router.post("/{flow_id}/run", response_model=ApiResponse[FlowRunResponse])
async def run_flow(
    flow_id: UUID,
    body: FlowRunRequest,
    ctx: TenantContext = Depends(require_permissions("flow:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).run(flow_id, body))
