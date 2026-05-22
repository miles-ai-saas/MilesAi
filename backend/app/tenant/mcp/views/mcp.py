"""MCP 服务 HTTP API：注册、同步工具列表与试调用。"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.common.schema import ApiResponse, PageParams, PageResult
from app.tenant.mcp.schemas.mcp import (
    McpServiceCreate,
    McpServiceOut,
    McpSyncResult,
    McpToolInvokeRequest,
    McpToolInvokeResult,
)
from app.tenant.mcp.services.mcp import McpServiceManager

router = APIRouter()


@router.get("", response_model=ApiResponse[PageResult[McpServiceOut]])
async def list_mcp(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("mcp:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await McpServiceManager(db, ctx).list_services(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[McpServiceOut])
async def create_mcp(
    body: McpServiceCreate,
    ctx: TenantContext = Depends(require_permissions("mcp:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await McpServiceManager(db, ctx).create_service(body))


@router.get("/{service_id}", response_model=ApiResponse[McpServiceOut])
async def get_mcp(
    service_id: UUID,
    ctx: TenantContext = Depends(require_permissions("mcp:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await McpServiceManager(db, ctx).get_service(service_id))


@router.delete("/{service_id}", response_model=ApiResponse[None])
async def delete_mcp(
    service_id: UUID,
    ctx: TenantContext = Depends(require_permissions("mcp:write")),
    db: AsyncSession = Depends(get_db),
):
    await McpServiceManager(db, ctx).delete_service(service_id)
    return ok(message="已删除")


@router.post("/{service_id}/sync", response_model=ApiResponse[McpSyncResult])
async def sync_mcp(
    service_id: UUID,
    ctx: TenantContext = Depends(require_permissions("mcp:write")),
    db: AsyncSession = Depends(get_db),
):
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
    return ok(await McpServiceManager(db, ctx).invoke_tool(service_id, tool_name, body))
