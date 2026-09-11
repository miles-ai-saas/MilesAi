"""钩子定义与绑定 HTTP API（智能体/流程等 scope 挂载）。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.infra.db import get_db
from miles_core.deps import get_page_params, require_permissions
from miles_common.response import ok, page_ok
from miles_core.tenant import TenantContext
from miles_common.schema import ApiResponse, PageParams, PageResult
from miles_portal.tenant.hooks.schemas.execution import HookExecutionLogOut
from miles_portal.tenant.hooks.schemas.meta import HookMetaOut
from miles_portal.tenant.hooks.schemas.hook import (
    HookBindingCreate,
    HookBindingOut,
    HookDefinitionCreate,
    HookDefinitionOut,
    HookDefinitionUpdate,
)
from miles_portal.tenant.hooks.services.hook import HookService

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> HookService:
    return HookService(db, ctx)


# GET */meta：枚举展示字典，须在 /{id} 等路径参数路由之前注册
@router.get("/meta", response_model=ApiResponse[HookMetaOut])
async def hook_meta(
    ctx: TenantContext = Depends(require_permissions("hook:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_meta())


@router.get("/executions", response_model=ApiResponse[PageResult[HookExecutionLogOut]])
async def list_hook_executions(
    hook_id: UUID | None = Query(None),
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("hook:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_executions(params, hook_id=hook_id)
    return page_ok(result.items, result.total, result.page, result.size)


@router.get("", response_model=ApiResponse[PageResult[HookDefinitionOut]])
async def list_hooks(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("hook:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_hooks(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[HookDefinitionOut])
async def create_hook(
    body: HookDefinitionCreate,
    ctx: TenantContext = Depends(require_permissions("hook:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).create_hook(body))


@router.patch("/{hook_id}", response_model=ApiResponse[HookDefinitionOut])
async def update_hook(
    hook_id: UUID,
    body: HookDefinitionUpdate,
    ctx: TenantContext = Depends(require_permissions("hook:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).update_hook(hook_id, body))


@router.delete("/{hook_id}", response_model=ApiResponse[None])
async def delete_hook(
    hook_id: UUID,
    ctx: TenantContext = Depends(require_permissions("hook:write")),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db, ctx).delete_hook(hook_id)
    return ok(message="已删除")


@router.get("/{hook_id}/bindings", response_model=ApiResponse[list[HookBindingOut]])
async def list_hook_bindings(
    hook_id: UUID,
    ctx: TenantContext = Depends(require_permissions("hook:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).list_bindings(hook_id))


@router.post("/{hook_id}/bindings", response_model=ApiResponse[HookBindingOut])
async def create_hook_binding(
    hook_id: UUID,
    body: HookBindingCreate,
    ctx: TenantContext = Depends(require_permissions("hook:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).create_binding(hook_id, body))


@router.delete("/bindings/{binding_id}", response_model=ApiResponse[None])
async def delete_hook_binding(
    binding_id: UUID,
    ctx: TenantContext = Depends(require_permissions("hook:write")),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db, ctx).delete_binding(binding_id)
    return ok(message="已删除")
