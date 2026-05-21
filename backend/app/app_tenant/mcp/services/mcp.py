from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundError
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.app_tenant.mcp.models import McpService, McpStatus
from app.app_tenant.mcp.schemas.mcp import McpServiceCreate, McpServiceOut, McpSyncResult
from app.app_tenant.mcp.sync import fetch_mcp_tools
from app.common.schema import PageParams, PageResult
from app.core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from app.core.service import BaseService


class McpServiceManager(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def get_service(self, service_id: UUID) -> McpServiceOut:
        row = await self.db.get(McpService, service_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("MCP 服务不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return McpServiceOut.model_validate(row)

    async def delete_service(self, service_id: UUID) -> None:
        row = await self.db.get(McpService, service_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("MCP 服务不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        await mark_deleted(self.db, row)

    async def list_services(self, params: PageParams) -> PageResult[McpServiceOut]:
        filters = [*tenant_filters(self.ctx, McpService.tenant_id), not_deleted(McpService)]
        total = await self.db.scalar(
            select(func.count(McpService.id)).where(*filters)
        )
        stmt = (
            select(McpService)
            .where(*filters)
            .order_by(McpService.created_at.desc())
            .offset((params.page - 1) * params.size)
            .limit(params.size)
        )
        items = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[McpServiceOut.model_validate(i) for i in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def create_service(self, body: McpServiceCreate) -> McpServiceOut:
        row = McpService(
            tenant_id=self.ctx.tenant_id,
            name=body.name,
            endpoint_url=body.endpoint_url,
            transport=body.transport,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return McpServiceOut.model_validate(row)

    async def sync_service(self, service_id: UUID) -> McpSyncResult:
        row = await self.db.get(McpService, service_id)
        if not row:
            raise NotFoundError("MCP 服务不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        tools = await fetch_mcp_tools(row.endpoint_url, row.transport)
        if not tools:
            tools = [
                {
                    "name": f"{row.name}_placeholder",
                    "description": "端点未返回工具列表（请确认 MCP 服务支持 tools/list）",
                }
            ]
        now = datetime.now(timezone.utc)
        row.tools_cache = tools
        row.last_sync_at = now
        row.status = McpStatus.ACTIVE
        await self.db.flush()
        return McpSyncResult(tools=tools, synced_at=now)
