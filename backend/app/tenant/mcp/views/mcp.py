"""
MCP 服务 HTTP API（前缀 /mcp）。

权限：mcp:read（列表/详情/试调用）、mcp:write（增删改/sync）。
协议实现见 app.tenant.mcp.client / sse_transport。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.common.schema import ApiResponse, PageParams, PageResult
from app.tenant.mcp.schemas.mcp import (
    McpServiceCreate,
    McpServiceOut,
    McpServiceUpdate,
    McpSyncResult,
    McpToolInvokeRequest,
    McpToolInvokeResult,
)
from app.tenant.mcp.services.mcp import McpServiceManager

router = APIRouter()


@router.get("", response_model=ApiResponse[PageResult[McpServiceOut]])
async def list_mcp(
    params: PageParams = Depends(get_page_params),
    transport: str | None = Query(None, description="http | sse | stdio，空为全部"),
    ctx: TenantContext = Depends(require_permissions("mcp:read")),
    db: AsyncSession = Depends(get_db),
):
    """分页列表，支持按传输类型 Tab 筛选。"""
    result = await McpServiceManager(db, ctx).list_services(params, transport_tab=transport)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[McpServiceOut])
async def create_mcp(
    body: McpServiceCreate,
    ctx: TenantContext = Depends(require_permissions("mcp:write")),
    db: AsyncSession = Depends(get_db),
):
    """注册 MCP 服务（创建后需 sync 拉取 tools/list）。"""
    return ok(await McpServiceManager(db, ctx).create_service(body))


@router.get("/{service_id}", response_model=ApiResponse[McpServiceOut])
async def get_mcp(
    service_id: UUID,
    ctx: TenantContext = Depends(require_permissions("mcp:read")),
    db: AsyncSession = Depends(get_db),
):
    """单条详情。"""
    return ok(await McpServiceManager(db, ctx).get_service(service_id))


@router.patch("/{service_id}", response_model=ApiResponse[McpServiceOut])
async def update_mcp(
    service_id: UUID,
    body: McpServiceUpdate,
    ctx: TenantContext = Depends(require_permissions("mcp:write")),
    db: AsyncSession = Depends(get_db),
):
    """编辑名称、端点、transport、connection_config 等。"""
    return ok(await McpServiceManager(db, ctx).update_service(service_id, body))


@router.delete("/{service_id}", response_model=ApiResponse[None])
async def delete_mcp(
    service_id: UUID,
    ctx: TenantContext = Depends(require_permissions("mcp:write")),
    db: AsyncSession = Depends(get_db),
):
    """软删除。"""
    await McpServiceManager(db, ctx).delete_service(service_id)
    return ok(message="已删除")


@router.post("/{service_id}/sync", response_model=ApiResponse[McpSyncResult])
async def sync_mcp(
    service_id: UUID,
    ctx: TenantContext = Depends(require_permissions("mcp:write")),
    db: AsyncSession = Depends(get_db),
):
    """远程 tools/list，写入 tools_cache 并更新 status / sync_error。"""
    return ok(await McpServiceManager(db, ctx).sync_service(service_id))


@router.post(
    "/{service_id}/tools/{tool_name}/invoke",
    response_model=ApiResponse[McpToolInvokeResult],
)
async def invoke_mcp_tool(
    service_id: UUID,
    tool_name: str,
    body: McpToolInvokeRequest,
    ctx: TenantContext = Depends(require_permissions("mcp:read")),
    db: AsyncSession = Depends(get_db),
):
    """试调用 tools/call；tool_name 须存在于该服务 tools_cache。"""
    return ok(await McpServiceManager(db, ctx).invoke_tool(service_id, tool_name, body))
