"""
工具调用入口：确认策略、Hook 与审计日志。

业务与 Flow 节点应优先使用 ``invoke_tool_with_context``；``invoke_tool_by_name`` 为内部路径（无确认/日志包装）。
"""

import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, NotFoundError
from app.common.trace import get_trace_id
from app.core.soft_delete import is_marked_deleted
from app.core.tenant import TenantContext
from app.tenant.hooks.models import HookScope, HookTrigger
from app.tenant.hooks.services.runner import HookRunner
from app.tenant.tools.builtin_registry import BUILTIN_SLUGS, SKILL_BOUND_SLUGS
from app.tenant.tools.confirmation import ToolConfirmationRequired, resolve_tool_meta
from app.tenant.tools.invoke.builtin import invoke_builtin
from app.tenant.tools.invoke.custom import invoke_custom_http, invoke_custom_script
from app.tenant.tools.invocation_log import write_tool_invocation_log
from app.tenant.tools.models import Tool, ToolType


async def resolve_bound_skill_id_from_agent(
    db: AsyncSession,
    agent_id: UUID | None,
) -> UUID | None:
    """从智能体 config 解析绑定的技能包 ID。"""
    if not agent_id:
        return None
    from app.models.agent import Agent

    agent = await db.get(Agent, agent_id)
    if not agent or not isinstance(agent.config, dict):
        return None
    raw = agent.config.get("skill_package_id")
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except ValueError:
        return None


async def invoke_tool_by_name(
    db: AsyncSession,
    ctx: TenantContext,
    name: str,
    params: dict,
    *,
    tool_id: UUID | None = None,
    bound_skill_id: UUID | None = None,
    actor_user_id: UUID | None = None,
    agent_id: UUID | None = None,
) -> dict:
    """按 slug 执行；不含确认与日志（内部用）。"""
    if name in BUILTIN_SLUGS and not tool_id:
        return await invoke_builtin(
            name,
            params,
            db=db,
            ctx=ctx,
            bound_skill_id=bound_skill_id,
            actor_user_id=actor_user_id,
            agent_id=agent_id,
        )

    if tool_id:
        tool = await db.get(Tool, tool_id)
    else:
        from sqlalchemy import select

        tool = await db.scalar(
            select(Tool).where(
                Tool.tenant_id == ctx.tenant_id,
                Tool.slug == name,
                Tool.is_active.is_(True),
            )
        )
    if not tool or is_marked_deleted(tool):
        raise NotFoundError("工具不存在")
    if tool.tool_type == ToolType.HTTP:
        return await invoke_custom_http(tool, params)
    if tool.tool_type == ToolType.SCRIPT:
        return await invoke_custom_script(db, tool, params, ctx=ctx, actor_user_id=ctx.user_id)
    raise BadRequestError(f"暂不支持执行工具类型: {tool.tool_type}")


async def invoke_tool_with_context(
    db: AsyncSession,
    ctx: TenantContext,
    name: str,
    params: dict,
    *,
    tool_id: UUID | None = None,
    confirmed: bool = False,
    actor_user_id: UUID | None = None,
    agent_id: UUID | None = None,
    invoke_source: str = "api",
) -> dict:
    """带确认策略、Hook 与审计日志的工具调用入口。

    链路：resolve_tool_meta → 确认校验 → BEFORE_TOOL Hook → invoke_tool_by_name
    → 写 invocation_log → AFTER_TOOL Hook。
    """
    meta = await resolve_tool_meta(db, ctx, name, tool_id=tool_id)
    slug = meta["slug"]
    resolved_tool_id = meta.get("tool_id") or tool_id
    tool_params = dict(params)

    # 生图：输入区张数覆盖 LLM 参数（须在确认门槛前生效）
    if slug == "generate_image":
        from app.integrations.generative.request_prefs import resolve_image_n

        tool_params["n"] = resolve_image_n(tool_params.get("n"))

    if meta["require_confirmation"] and not confirmed:
        await write_tool_invocation_log(
            db,
            tenant_id=ctx.tenant_id,
            tool_slug=slug,
            tool_id=resolved_tool_id,
            source=meta["source"],
            status="confirmation_required",
            params=tool_params,
            actor_user_id=actor_user_id,
            agent_id=agent_id,
            invoke_source=invoke_source,
            trace_id=get_trace_id(),
        )
        raise ToolConfirmationRequired(slug, meta["name"], meta.get("description"), tool_params)

    if slug == "generate_image":
        from app.integrations.generative.policy import (
            image_tool_confirmation_message,
            needs_image_tool_confirmation,
        )

        if needs_image_tool_confirmation(tool_params) and not confirmed:
            await write_tool_invocation_log(
                db,
                tenant_id=ctx.tenant_id,
                tool_slug=slug,
                tool_id=resolved_tool_id,
                source=meta["source"],
                status="confirmation_required",
                params=tool_params,
                actor_user_id=actor_user_id,
                agent_id=agent_id,
                invoke_source=invoke_source,
                trace_id=get_trace_id(),
            )
            raise ToolConfirmationRequired(
                slug,
                meta["name"],
                image_tool_confirmation_message(tool_params),
                tool_params,
            )

    bound_skill_id: UUID | None = None
    if slug in SKILL_BOUND_SLUGS:
        bound_skill_id = await resolve_bound_skill_id_from_agent(db, agent_id)
        if not bound_skill_id:
            raise BadRequestError("该工具需要智能体绑定技能包（config.skill_package_id）")

    hook_runner = HookRunner(db, ctx.tenant_id)
    tool_scope_id = resolved_tool_id
    hook_base = {
        "module": "tool_invoke",
        "tool_slug": slug,
        "tool_id": str(tool_scope_id) if tool_scope_id else None,
        "params": tool_params,
        "agent_id": str(agent_id) if agent_id else None,
        "invoke_source": invoke_source,
    }
    before = await hook_runner.run(
        HookTrigger.BEFORE_TOOL,
        HookScope.TOOL,
        tool_scope_id,
        hook_base,
    )
    tool_params = dict(before.payload.get("params", tool_params))

    started = time.monotonic()
    try:
        output = await invoke_tool_by_name(
            db,
            ctx,
            slug,
            tool_params,
            tool_id=resolved_tool_id,
            bound_skill_id=bound_skill_id,
            actor_user_id=actor_user_id or ctx.user_id,
            agent_id=agent_id,
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        await write_tool_invocation_log(
            db,
            tenant_id=ctx.tenant_id,
            tool_slug=slug,
            tool_id=resolved_tool_id,
            source=meta["source"],
            status="success",
            params=tool_params,
            output=output,
            latency_ms=latency_ms,
            actor_user_id=actor_user_id,
            agent_id=agent_id,
            invoke_source=invoke_source,
            trace_id=get_trace_id(),
        )
        await hook_runner.run(
            HookTrigger.AFTER_TOOL,
            HookScope.TOOL,
            tool_scope_id,
            {
                **hook_base,
                "params": tool_params,
                "output": output,
                "status": "success",
                "latency_ms": latency_ms,
            },
        )
        return output
    except ToolConfirmationRequired:
        raise
    except Exception as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        await write_tool_invocation_log(
            db,
            tenant_id=ctx.tenant_id,
            tool_slug=slug,
            tool_id=resolved_tool_id,
            source=meta["source"],
            status="error",
            params=params,
            error_message=str(exc)[:2000],
            latency_ms=latency_ms,
            actor_user_id=actor_user_id,
            agent_id=agent_id,
            invoke_source=invoke_source,
            trace_id=get_trace_id(),
        )
        raise
