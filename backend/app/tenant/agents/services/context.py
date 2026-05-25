"""
智能体 system prompt 增强块（技能包 + MCP 工具目录）。

由 ``AgentService._resolve_system_prompt`` 拼接到基础 ``system_prompt`` 之后；
**不**执行 MCP invoke，仅把 ``tools_cache`` 名称/描述注入提示词供 LLM 或 tool_agent 选用。

与 RAG：知识库检索走 ``knowledge_bases`` 绑定，与本模块独立。
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant.mcp.models import McpService
from app.tenant.skills.models import SkillPackage
from app.tenant.skills.storage import read_skill_md
from app.core.soft_delete import is_marked_deleted, not_deleted
from app.core.tenant import TenantContext, tenant_filters


async def build_skill_mcp_prompt_block(
    db: AsyncSession,
    ctx: TenantContext,
    config: dict,
) -> str:
    """将 agent.config 中的技能包与 MCP 工具说明拼入 system prompt。"""
    parts: list[str] = []
    # 单技能绑定：AgentForm 写入 config.skill_package_id
    skill_id = config.get("skill_package_id")
    if skill_id:
        try:
            sid = UUID(str(skill_id))
        except ValueError:
            sid = None
        if sid:
            skill = await db.get(SkillPackage, sid)
            if skill and skill.tenant_id == ctx.tenant_id and skill.is_active and not is_marked_deleted(skill):
                block = f"【技能包 · {skill.name}】"
                # 优先磁盘 SKILL.md（与编辑器保存一致），无文件再回退 DB prompt_snippet
                body = read_skill_md(ctx.tenant_id, skill.slug) if skill.slug else ""
                if body.strip():
                    block += f"\n{body.strip()}"
                elif skill.prompt_snippet:
                    block += f"\n{skill.prompt_snippet.strip()}"
                if skill.tool_names:
                    tools = ", ".join(skill.tool_names)
                    block += f"\n可用工具: {tools}"
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
