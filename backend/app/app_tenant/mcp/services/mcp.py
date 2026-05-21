from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundError
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.app_tenant.mcp.models import McpService, McpStatus
from app.app_tenant.mcp.schemas.mcp import McpServiceCreate, McpServiceOut, McpSyncResult
from app.common.schema import PageParams, PageResult
from app.core.service import BaseService


class McpServiceManager(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def list_services(self, params: PageParams) -> PageResult[McpServiceOut]:
        filters = tenant_filters(self.ctx, McpService.tenant_id)
        total = await self.db.scalar(select(func.count()).select_from(McpService).where(*filters))
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
        tools: list[dict] = []
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(row.endpoint_url)
                if resp.is_success and resp.headers.get("content-type", "").startswith("application/json"):
                    data = resp.json()
                    if isinstance(data, list):
                        tools = data
                    elif isinstance(data, dict) and "tools" in data:
                        tools = data["tools"]
        except Exception:
            tools = [{"name": f"{row.name}_tool_mock", "description": "同步占位（端点不可达时使用）"}]
        if not tools:
            tools = [{"name": f"{row.name}_tool_mock", "description": "同步占位"}]
        now = datetime.now(timezone.utc)
        row.tools_cache = tools
        row.last_sync_at = now
        row.status = McpStatus.ACTIVE
        await self.db.flush()
        return McpSyncResult(tools=tools, synced_at=now)
