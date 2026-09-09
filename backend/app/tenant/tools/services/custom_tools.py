"""租户自定义工具 DB 加载与对话工具装配（L1）。

``load_custom_tool_specs``：``Tool`` 表 HTTP/SCRIPT 行 → 中性 ``CustomToolSpec``；
``assemble_agent_tools``：specs + 内置/技能/生成壳（``build_platform_tools``）组装
为对话工具 schema 列表。原 ``integrations/langchain/tools.load_tenant_custom_tools``
的 DB 查询职责上移本模块，L3 只保留纯构造。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.soft_delete import append_not_deleted
from app.core.tenant import TenantContext, tenant_filters
from app.integrations.langchain.tools import CustomToolSpec, build_platform_tools
from app.tenant.tools.models import Tool, ToolType


async def load_custom_tool_specs(db: AsyncSession, ctx: TenantContext) -> list[CustomToolSpec]:
    """加载租户启用的自定义 HTTP / 脚本工具为中性 spec（不构造 StructuredTool）。"""
    filters = append_not_deleted(tenant_filters(ctx, Tool.tenant_id), Tool)
    rows = (
        (
            await db.execute(
                select(Tool).where(
                    *filters,
                    Tool.is_active.is_(True),
                    Tool.tool_type.in_([ToolType.HTTP, ToolType.SCRIPT]),
                )
            )
        )
        .scalars()
        .all()
    )
    return [
        CustomToolSpec(
            slug=t.slug,
            name=t.name,
            description=t.description,
            tool_type=t.tool_type.value if hasattr(t.tool_type, "value") else str(t.tool_type),
            parameters=list(t.parameters or []),
        )
        for t in rows
    ]


async def assemble_agent_tools(
    db: AsyncSession,
    ctx: TenantContext,
    agent_config: dict | None,
) -> list:
    """装配对话工具 schema 列表（specs 上移 L1 + L3 纯构造）。"""
    specs = await load_custom_tool_specs(db, ctx)
    return build_platform_tools(agent_config, specs)
