"""
A2A 外部智能体 Peer HTTP API（``/a2a/peers``）。

同步 Card 后 ``status=active`` 方可被 Agent 引用；``probe`` 可在登记前探测 URL。
对话调用不在此路由，见 ``AgentService.chat`` → ``tenant.a2a.invoke``。
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant.a2a.schemas.meta import A2aMetaOut
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
    """构造 A2A Peer 用例服务。"""
    return A2aPeerService(db, ctx)


@router.get("", response_model=ApiResponse[PageResult[A2aPeerOut]])
async def list_a2a_peers(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    """分页列出外部 A2A Agent。"""
    result = await _svc(db, ctx).list_peers(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[A2aPeerOut])
async def create_a2a_peer(
    body: A2aPeerCreate,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    """登记外部 Agent（初始 PENDING）。"""
    return ok(await _svc(db, ctx).create_peer(body))


@router.post("/probe", response_model=ApiResponse[A2aPeerProbeResult])
async def probe_a2a_peer(
    body: A2aProbeRequest,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    """登记前探测 Card 是否可访问。"""
    return ok(await _svc(db, ctx).probe_url(body.base_url))


# GET */meta：枚举展示字典，须在 /{id} 等路径参数路由之前注册
@router.get("/meta", response_model=ApiResponse[A2aMetaOut])
async def a2a_peers_meta(
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_meta())


@router.get("/{peer_id}", response_model=ApiResponse[A2aPeerOut])
async def get_a2a_peer(
    peer_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    """获取 Peer 详情。"""
    return ok(await _svc(db, ctx).get_peer(peer_id))


@router.patch("/{peer_id}", response_model=ApiResponse[A2aPeerOut])
async def update_a2a_peer(
    peer_id: UUID,
    body: A2aPeerUpdate,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    """更新 Peer 元数据。"""
    return ok(await _svc(db, ctx).update_peer(peer_id, body))


@router.delete("/{peer_id}", response_model=ApiResponse[None])
async def delete_a2a_peer(
    peer_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    """软删 Peer。"""
    await _svc(db, ctx).delete_peer(peer_id)
    return ok(message="已删除")


@router.post("/{peer_id}/sync-card", response_model=ApiResponse[A2aPeerSyncResult])
async def sync_a2a_peer_card(
    peer_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    """拉取 Agent Card 并更新 ACTIVE/ERROR 状态。"""
    return ok(await _svc(db, ctx).sync_peer_card(peer_id))
