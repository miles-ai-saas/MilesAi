from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext, tenant_filters
from app.app_tenant.tools.models import Tool
from app.common.schema import PageParams, PageResult
from app.app_tenant.tools.schemas.tools import ToolCreate, ToolOut
from app.core.service import BaseService

BUILTIN_TOOLS = [
    {"name": "knowledge_search", "description": "检索租户知识库"},
    {"name": "http_request", "description": "发起 HTTP 请求"},
    {"name": "calculator", "description": "简单数学表达式计算"},
]


class ToolsService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def list_tools(self, params: PageParams) -> PageResult[ToolOut]:
        filters = tenant_filters(self.ctx, Tool.tenant_id)
        total = await self.db.scalar(select(func.count()).select_from(Tool).where(*filters))
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
            name=body.name,
            description=body.description,
            tool_type=body.tool_type,
            config=body.config,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return ToolOut.model_validate(row)

    async def list_builtin(self) -> list[dict]:
        return BUILTIN_TOOLS
