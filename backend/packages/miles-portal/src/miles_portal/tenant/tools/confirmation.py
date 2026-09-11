"""工具确认策略与元数据解析。"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError
from miles_core.tenant import TenantContext
from miles_ai.integrations.langchain.tools import is_mcp_tool_name
from miles_portal.tenant.tools.builtin_registry import get_builtin
from miles_portal.tenant.tools.models import Tool
from miles_core.soft_delete import is_marked_deleted


class ToolConfirmationRequired(BadRequestError):
    """工具需要用户确认后才能执行。"""

    def __init__(self, slug: str, name: str, description: str | None, params: dict) -> None:
        self.slug = slug
        self.tool_name = name
        self.tool_description = description
        self.params = params
        super().__init__(f"工具「{name}」需要确认后执行")


async def resolve_tool_meta(
    db: AsyncSession,
    ctx: TenantContext,
    slug: str,
    *,
    tool_id: UUID | None = None,
) -> dict:
    """返回 slug、name、description、require_confirmation、source、tool_id。"""
    if tool_id:
        tool = await db.get(Tool, tool_id)
        if not tool or is_marked_deleted(tool) or tool.tenant_id != ctx.tenant_id:
            raise BadRequestError("工具不存在")
        return {
            "slug": tool.slug,
            "name": tool.name,
            "description": tool.description,
            "require_confirmation": tool.require_confirmation,
            "source": "custom",
            "tool_id": tool.id,
        }

    builtin = get_builtin(slug)
    if builtin:
        return {
            "slug": builtin["slug"],
            "name": builtin["name"],
            "description": builtin.get("description"),
            "require_confirmation": bool(builtin.get("require_confirmation")),
            "source": "builtin",
            "tool_id": None,
        }

    if is_mcp_tool_name(slug):
        from miles_portal.tenant.tools.services.mcp_tools import resolve_mcp_tool_meta

        meta = await resolve_mcp_tool_meta(db, ctx, slug)
        if not meta:
            raise BadRequestError("MCP 工具不存在或服务未同步")
        return meta

    tool = await db.scalar(
        select(Tool).where(
            Tool.tenant_id == ctx.tenant_id,
            Tool.slug == slug,
            Tool.is_active.is_(True),
        )
    )
    if not tool or is_marked_deleted(tool):
        raise BadRequestError("工具不存在")
    return {
        "slug": tool.slug,
        "name": tool.name,
        "description": tool.description,
        "require_confirmation": tool.require_confirmation,
        "source": "custom",
        "tool_id": tool.id,
    }
