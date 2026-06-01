"""合同管理 HTTP API，路由前缀 `/biz/contracts`。

提供合同的 CRUD 接口，支持按项目和状态筛选。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.schemas.contract import BizContractCreate, BizContractOut, BizContractUpdate
from app.biz.services.contract import ContractService
from app.common.response import ok, page_ok
from app.common.schema import ApiResponse, PageResult
from app.core.deps import require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> ContractService:
    return ContractService(db, ctx)


@router.get("", response_model=ApiResponse[PageResult[BizContractOut]])
async def list_contracts(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    project_id: UUID | None = Query(None),
    client_id: UUID | None = Query(None),
    status: str | None = Query(None),
    ctx: TenantContext = Depends(require_permissions("biz:contract:read")),
    db: AsyncSession = Depends(get_db),
):
    """分页查询合同列表，支持按项目、客户和状态筛选。"""
    result = await _svc(db, ctx).list_contracts(page=page, size=size, project_id=project_id, client_id=client_id, status=status)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[BizContractOut])
async def create_contract(
    body: BizContractCreate,
    ctx: TenantContext = Depends(require_permissions("biz:contract:write")),
    db: AsyncSession = Depends(get_db),
):
    """创建新合同。"""
    return ok(await _svc(db, ctx).create(body))


@router.get("/{contract_id}", response_model=ApiResponse[BizContractOut])
async def get_contract(
    contract_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:contract:read")),
    db: AsyncSession = Depends(get_db),
):
    """获取单个合同详情。"""
    return ok(await _svc(db, ctx).get(contract_id))


@router.patch("/{contract_id}", response_model=ApiResponse[BizContractOut])
async def update_contract(
    contract_id: UUID,
    body: BizContractUpdate,
    ctx: TenantContext = Depends(require_permissions("biz:contract:write")),
    db: AsyncSession = Depends(get_db),
):
    """更新合同信息。"""
    return ok(await _svc(db, ctx).update(contract_id, body))


@router.delete("/{contract_id}", response_model=ApiResponse[None])
async def delete_contract(
    contract_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:contract:write")),
    db: AsyncSession = Depends(get_db),
):
    """删除合同。"""
    await _svc(db, ctx).delete(contract_id)
    return ok(message="已删除")
