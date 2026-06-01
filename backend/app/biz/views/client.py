"""客户管理 HTTP API，路由前缀 `/biz/clients`。

提供客户的 CRUD 接口，以及客户下联系人的管理接口。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.schemas.client import BizClientContactCreate, BizClientContactOut, BizClientCreate, BizClientOut, BizClientUpdate
from app.biz.services.client import ClientService
from app.common.response import ok, page_ok
from app.common.schema import ApiResponse, PageResult
from app.core.deps import require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> ClientService:
    return ClientService(db, ctx)


@router.get("", response_model=ApiResponse[PageResult[BizClientOut]])
async def list_clients(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    ctx: TenantContext = Depends(require_permissions("biz:client:read")),
    db: AsyncSession = Depends(get_db),
):
    """分页查询客户列表，支持名称搜索。"""
    result = await _svc(db, ctx).list_clients(page=page, size=size, search=search)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[BizClientOut])
async def create_client(
    body: BizClientCreate,
    ctx: TenantContext = Depends(require_permissions("biz:client:write")),
    db: AsyncSession = Depends(get_db),
):
    """创建新客户。"""
    return ok(await _svc(db, ctx).create_client(body))


@router.get("/{client_id}", response_model=ApiResponse[BizClientOut])
async def get_client(
    client_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:client:read")),
    db: AsyncSession = Depends(get_db),
):
    """获取单个客户详情。"""
    return ok(await _svc(db, ctx).get_client(client_id))


@router.patch("/{client_id}", response_model=ApiResponse[BizClientOut])
async def update_client(
    client_id: UUID,
    body: BizClientUpdate,
    ctx: TenantContext = Depends(require_permissions("biz:client:write")),
    db: AsyncSession = Depends(get_db),
):
    """更新客户信息。"""
    return ok(await _svc(db, ctx).update_client(client_id, body))


@router.delete("/{client_id}", response_model=ApiResponse[None])
async def delete_client(
    client_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:client:write")),
    db: AsyncSession = Depends(get_db),
):
    """删除客户。"""
    await _svc(db, ctx).delete_client(client_id)
    return ok(message="已删除")


# ── contacts ──

@router.get("/{client_id}/contacts", response_model=ApiResponse[list[BizClientContactOut]])
async def list_contacts(
    client_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:client:read")),
    db: AsyncSession = Depends(get_db),
):
    """获取客户下的联系人列表。"""
    return ok(await _svc(db, ctx).list_contacts(client_id))


@router.post("/{client_id}/contacts", response_model=ApiResponse[BizClientContactOut])
async def create_contact(
    client_id: UUID,
    body: BizClientContactCreate,
    ctx: TenantContext = Depends(require_permissions("biz:client:write")),
    db: AsyncSession = Depends(get_db),
):
    """为客户添加联系人。"""
    return ok(await _svc(db, ctx).create_contact(client_id, body))


@router.patch("/{client_id}/contacts/{contact_id}", response_model=ApiResponse[BizClientContactOut])
async def update_contact(
    client_id: UUID,
    contact_id: UUID,
    body: BizClientContactCreate,
    ctx: TenantContext = Depends(require_permissions("biz:client:write")),
    db: AsyncSession = Depends(get_db),
):
    """更新联系人信息。"""
    return ok(await _svc(db, ctx).update_contact(contact_id, body))


@router.delete("/{client_id}/contacts/{contact_id}", response_model=ApiResponse[None])
async def delete_contact(
    client_id: UUID,
    contact_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:client:write")),
    db: AsyncSession = Depends(get_db),
):
    """删除联系人。"""
    await _svc(db, ctx).delete_contact(contact_id)
    return ok(message="已删除")
