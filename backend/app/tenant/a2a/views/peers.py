"""A2A 外部智能体 Peer：登记、Agent Card 同步与连通性探测。"""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant.a2a.schemas.peer import (
    A2aPeerCreate,
    A2aPeerOut,
    A2aPeerProbeResult,
    A2aPeerSyncResult,
    A2aPeerUpdate,
)
from app.tenant.a2a.services.peers import A2aPeerService
from app.common.response import ok, page_ok
from app.common.schema import ApiResponse, PageParams, PageResult
from app.infra.db import get_db
from app.core.deps import get_page_params, require_permissions
from app.core.tenant import TenantContext

router = APIRouter()


class A2aProbeRequest(BaseModel):
    base_url: str = Field(..., min_length=1, max_length=1024)


def _svc(db: AsyncSession, ctx: TenantContext) -> A2aPeerService:
    return A2aPeerService(db, ctx)


@router.get("", response_model=ApiResponse[PageResult[A2aPeerOut]])
async def list_a2a_peers(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_peers(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[A2aPeerOut])
async def create_a2a_peer(
    body: A2aPeerCreate,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).create_peer(body))


@router.post("/probe", response_model=ApiResponse[A2aPeerProbeResult])
async def probe_a2a_peer(
    body: A2aProbeRequest,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).probe_url(body.base_url))


@router.get("/{peer_id}", response_model=ApiResponse[A2aPeerOut])
async def get_a2a_peer(
    peer_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_peer(peer_id))


@router.patch("/{peer_id}", response_model=ApiResponse[A2aPeerOut])
async def update_a2a_peer(
    peer_id: UUID,
    body: A2aPeerUpdate,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).update_peer(peer_id, body))


@router.delete("/{peer_id}", response_model=ApiResponse[None])
async def delete_a2a_peer(
    peer_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db, ctx).delete_peer(peer_id)
    return ok(message="已删除")


@router.post("/{peer_id}/sync-card", response_model=ApiResponse[A2aPeerSyncResult])
async def sync_a2a_peer_card(
    peer_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).sync_peer_card(peer_id))
