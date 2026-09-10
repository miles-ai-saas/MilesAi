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
from app.tenant.skills.skill_layout import format_layout_prompt_blocks
from app.tenant.skills.storage import read_skill_md
from app.integrations.langchain.tools import compose_mcp_tool_name
from app.tenant.tools.builtin_registry import BUILTIN_REGISTRY
from app.tenant.tools.models import Tool
from app.core.soft_delete import is_marked_deleted, not_deleted
from app.core.tenant import TenantContext, tenant_filters


def _format_param_summary(parameters: list | None) -> str:
    """将工具 parameters schema 压缩为一行「name(必填/可选)」摘要。"""
    if not parameters:
        return ""
    parts: list[str] = []
    for p in parameters[:8]:
        if not isinstance(p, dict):
            continue
        name = p.get("name", "?")
        req = "必填" if p.get("required") else "可选"
        parts.append(f"{name}({req})")
    return ", ".join(parts)


async def _append_platform_tools_block(
    db: AsyncSession,
    ctx: TenantContext,
    config: dict,
    parts: list[str],
) -> None:
    """enable_tool_calling 时，将可选平台工具摘要写入 prompt（与 function schema 互补）。"""
    if not config.get("enable_tool_calling"):
        return
    raw_slugs = config.get("tool_slugs") or []
    if isinstance(raw_slugs, str):
        raw_slugs = [raw_slugs]
    slug_filter = {str(s) for s in raw_slugs if s}

    lines: list[str] = []
    skill_bound = bool(config.get("skill_package_id"))
    for t in BUILTIN_REGISTRY:
        slug = t["slug"]
        if t.get("skill_bound_only") and not skill_bound:
            continue
        if slug_filter and slug not in slug_filter:
            continue
        params = _format_param_summary(t.get("parameters"))
        suffix = f" 参数: {params}" if params else ""
        lines.append(f"- {slug}: {t.get('description', t.get('name', slug))}{suffix}")

    if slug_filter:
        custom_filters = [
            *tenant_filters(ctx, Tool.tenant_id),
            not_deleted(Tool),
            Tool.is_active.is_(True),
            Tool.slug.in_(slug_filter),
        ]
        custom_rows = (await db.execute(select(Tool).where(*custom_filters))).scalars().all()
        for row in custom_rows:
            params = _format_param_summary(row.parameters)
            suffix = f" 参数: {params}" if params else ""
            lines.append(f"- {row.slug}: {row.description or row.name}{suffix}")
    elif not slug_filter:
        custom_filters = [
            *tenant_filters(ctx, Tool.tenant_id),
            not_deleted(Tool),
            Tool.is_active.is_(True),
        ]
        custom_rows = (await db.execute(select(Tool).where(*custom_filters).limit(20))).scalars().all()
        for row in custom_rows:
            params = _format_param_summary(row.parameters)
            suffix = f" 参数: {params}" if params else ""
            lines.append(f"- {row.slug}: {row.description or row.name}{suffix}")

    if lines:
        parts.append("【平台工具 · 可 function calling 执行】\n" + "\n".join(lines[:24]))


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
                layout = (skill.config or {}).get("layout")
                for extra in format_layout_prompt_blocks(layout if isinstance(layout, dict) else None):
                    block += f"\n{extra}"
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
        callable_hint = bool(config.get("enable_tool_calling") or config.get("enable_generative_tools"))
        for svc in services:
            tools = [
                t
                for t in (svc.tools_cache or [])
                if isinstance(t, dict) and str(t.get("name") or "").strip() and not str(t["name"]).endswith("_placeholder")
            ]
            if not tools:
                parts.append(f"【MCP · {svc.name}】尚未同步工具，请先在市场/MCP 页同步。")
                continue
            lines = [
                f"- {compose_mcp_tool_name(svc.name, str(t.get('name')))}: {t.get('description', '')}"
                for t in tools[:12]
            ]
            suffix = "（可 function calling 自动调用）" if callable_hint else "（启用工具调用后可自动调用）"
            parts.append(f"【MCP · {svc.name}】{suffix}\n" + "\n".join(lines))

    await _append_platform_tools_block(db, ctx, config, parts)

    if not parts:
        return ""
    return "\n\n".join(parts)
