"""工具 HTTP API：内置工具目录、自定义工具 CRUD 与试调用。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.infra.db import get_db
from miles_core.deps import get_page_params, require_permissions
from miles_common.response import ok, page_ok
from miles_core.tenant import TenantContext
from miles_common.schema import ApiResponse, PageParams, PageResult
from miles_portal.tenant.tools.schemas.meta import ToolsMetaOut
from miles_portal.tenant.tools.schemas.tools import (
    ToolCatalogItem,
    ToolCreate,
    ToolInvokeRequest,
    ToolInvokeResult,
    ToolInvocationLogOut,
    ToolOut,
    ToolUpdate,
)
from miles_portal.tenant.tools.services.tools import ToolsService

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> ToolsService:
    return ToolsService(db, ctx)


# GET */meta：枚举展示字典，须在 /{id} 等路径参数路由之前注册
@router.get("/meta", response_model=ApiResponse[ToolsMetaOut])
async def tools_meta(
    ctx: TenantContext = Depends(require_permissions("tools:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_meta())


@router.get("/invocation-logs", response_model=ApiResponse[PageResult[ToolInvocationLogOut]])
async def list_invocation_logs(
    params: PageParams = Depends(get_page_params),
    tool_slug: str | None = Query(None),
    ctx: TenantContext = Depends(require_permissions("tools:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_invocation_logs(params, tool_slug=tool_slug)
    return page_ok(result.items, result.total, result.page, result.size)


@router.get("/catalog", response_model=ApiResponse[list[ToolCatalogItem]])
async def tool_catalog(
    source: str | None = Query(None, description="builtin | custom"),
    category_id: UUID | None = Query(None),
    tag_ids: list[UUID] | None = Query(None),
    ctx: TenantContext = Depends(require_permissions("tools:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).list_catalog(source=source, category_id=category_id, tag_ids=tag_ids))


@router.get("", response_model=ApiResponse[PageResult[ToolOut]])
async def list_tools(
    params: PageParams = Depends(get_page_params),
    category_id: UUID | None = Query(None),
    tag_ids: list[UUID] | None = Query(None, description="按标签筛选（任一匹配）"),
    ctx: TenantContext = Depends(require_permissions("tools:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_tools(params, category_id=category_id, tag_ids=tag_ids)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[ToolOut])
async def create_tool(
    body: ToolCreate,
    ctx: TenantContext = Depends(require_permissions("tools:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).create_tool(body))


@router.get("/{tool_id}", response_model=ApiResponse[ToolOut])
async def get_tool(
    tool_id: UUID,
    ctx: TenantContext = Depends(require_permissions("tools:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_tool(tool_id))


@router.patch("/{tool_id}", response_model=ApiResponse[ToolOut])
async def update_tool(
    tool_id: UUID,
    body: ToolUpdate,
    ctx: TenantContext = Depends(require_permissions("tools:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).update_tool(tool_id, body))


@router.delete("/{tool_id}", response_model=ApiResponse[None])
async def delete_tool(
    tool_id: UUID,
    ctx: TenantContext = Depends(require_permissions("tools:write")),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db, ctx).delete_tool(tool_id)
    return ok(message="已删除")


@router.post("/{tool_name}/invoke", response_model=ApiResponse[ToolInvokeResult])
async def invoke_tool(
    tool_name: str,
    body: ToolInvokeRequest,
    ctx: TenantContext = Depends(require_permissions("tools:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).invoke(tool_name, body))


@router.get("/builtin", response_model=ApiResponse[list[dict]])
async def list_builtin(
    ctx: TenantContext = Depends(require_permissions("tools:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).list_builtin())
