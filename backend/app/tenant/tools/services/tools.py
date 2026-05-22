from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundError
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.tenant.mcp.models import McpService
from app.tenant.tools.invoke import invoke_tool_by_name
from app.tenant.tools.models import Tool
from app.common.schema import PageParams, PageResult
from app.tenant.tools.schemas.tools import (
    ToolCatalogItem,
    ToolCreate,
    ToolInvokeRequest,
    ToolInvokeResult,
    ToolOut,
    ToolUpdate,
)
from app.core.soft_delete import append_not_deleted, is_marked_deleted, mark_deleted, not_deleted
from app.core.service import BaseService

BUILTIN_TOOLS = [
    {"name": "knowledge_search", "description": "检索租户知识库（params: query, kb_id）"},
    {"name": "http_request", "description": "发起 HTTP 请求（params: url, method）"},
    {"name": "calculator", "description": "安全计算表达式（params: expression）"},
]


class ToolsService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def list_tools(self, params: PageParams) -> PageResult[ToolOut]:
        filters = append_not_deleted(tenant_filters(self.ctx, Tool.tenant_id), Tool)
        total = await self.db.scalar(select(func.count(Tool.id)).where(*filters))
        stmt = (
            select(Tool)
            .where(*filters)
            .order_by(Tool.created_at.desc())
            .offset((params.page - 1) * params.size)
            .limit(params.size)
        )
        items = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[ToolOut.model_validate(i) for i in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def create_tool(self, body: ToolCreate) -> ToolOut:
        row = Tool(
            tenant_id=self.ctx.tenant_id,
            name=body.name.strip(),
            description=body.description,
            tool_type=body.tool_type,
            config=body.config,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return ToolOut.model_validate(row)

    async def update_tool(self, tool_id: UUID, body: ToolUpdate) -> ToolOut:
        row = await self._get_or_raise(tool_id)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(row, k, v)
        await self.db.flush()
        await self.db.refresh(row)
        return ToolOut.model_validate(row)

    async def delete_tool(self, tool_id: UUID) -> None:
        row = await self._get_or_raise(tool_id)
        await mark_deleted(self.db, row)

    async def invoke(self, name: str, body: ToolInvokeRequest) -> ToolInvokeResult:
        output = await invoke_tool_by_name(
            self.db,
            self.ctx,
            name,
            body.params,
            tool_id=body.tool_id,
        )
        source = "custom" if body.tool_id else "builtin"
        return ToolInvokeResult(tool=name, source=source, output=output)

    async def list_catalog(self) -> list[ToolCatalogItem]:
        catalog: list[ToolCatalogItem] = [
            ToolCatalogItem(
                source="builtin",
                name=t["name"],
                description=t.get("description"),
            )
            for t in BUILTIN_TOOLS
        ]
        filters = append_not_deleted(
            tenant_filters(self.ctx, Tool.tenant_id),
            Tool,
        )
        custom = (
            await self.db.execute(
                select(Tool).where(*filters, Tool.is_active.is_(True)).order_by(Tool.name)
            )
        ).scalars().all()
        for t in custom:
            catalog.append(
                ToolCatalogItem(
                    source="custom",
                    name=t.name,
                    description=t.description,
                    tool_id=t.id,
                )
            )
        mcp_filters = [*tenant_filters(self.ctx, McpService.tenant_id), not_deleted(McpService)]
        mcps = (await self.db.execute(select(McpService).where(*mcp_filters))).scalars().all()
        for svc in mcps:
            for tool in svc.tools_cache or []:
                if isinstance(tool, dict):
                    catalog.append(
                        ToolCatalogItem(
                            source="mcp",
                            name=str(tool.get("name", "tool")),
                            description=str(tool.get("description") or "") or None,
                            mcp_service_id=svc.id,
                            mcp_service_name=svc.name,
                        )
                    )
        return catalog

    async def list_builtin(self) -> list[dict]:
        return BUILTIN_TOOLS

    async def _get_or_raise(self, tool_id: UUID) -> Tool:
        row = await self.db.get(Tool, tool_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("工具不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row
