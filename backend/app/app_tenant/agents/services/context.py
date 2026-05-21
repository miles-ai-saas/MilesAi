"""智能体运行时上下文：技能包与 MCP 工具说明注入。"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app_tenant.mcp.models import McpService
from app.app_tenant.skills.models import SkillPackage
from app.core.soft_delete import is_marked_deleted, not_deleted
from app.core.tenant import TenantContext, tenant_filters


async def build_skill_mcp_prompt_block(
    db: AsyncSession,
    ctx: TenantContext,
    config: dict,
) -> str:
    parts: list[str] = []
    skill_id = config.get("skill_package_id")
    if skill_id:
        try:
            sid = UUID(str(skill_id))
        except ValueError:
            sid = None
        if sid:
            skill = await db.get(SkillPackage, sid)
            if skill and skill.tenant_id == ctx.tenant_id and skill.is_active and not is_marked_deleted(skill):
                tools = ", ".join(skill.tool_names) if skill.tool_names else "无"
                block = f"【技能包 · {skill.name}】可用工具: {tools}"
                if skill.prompt_snippet:
                    block += f"\n{skill.prompt_snippet.strip()}"
                parts.append(block)

    raw_mcp = config.get("mcp_service_ids") or []
    if isinstance(raw_mcp, str):
        raw_mcp = [raw_mcp]
    mcp_ids: list[UUID] = []
    for item in raw_mcp:
        try:
            mcp_ids.append(UUID(str(item)))
        except ValueError:
            continue
    if mcp_ids:
        filters = tenant_filters(ctx, McpService.tenant_id)
        stmt = select(McpService).where(McpService.id.in_(mcp_ids), *filters)
        services = (await db.execute(stmt)).scalars().all()
        for svc in services:
            tools = svc.tools_cache or []
            if not tools:
                parts.append(f"【MCP · {svc.name}】尚未同步工具，请先在市场/MCP 页同步。")
                continue
            lines = [f"- {t.get('name', 'tool')}: {t.get('description', '')}" for t in tools[:12]]
            parts.append(f"【MCP · {svc.name}】\n" + "\n".join(lines))

    if not parts:
        return ""
    return "\n\n".join(parts)
