"""
工具调用入口：确认策略、Hook 与审计日志。

业务与 Flow 节点应优先使用 ``invoke_tool_with_context``；``invoke_tool_by_name`` 为内部路径（无确认/日志包装）。
"""

import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_common.trace import get_trace_id
from miles_core.soft_delete import is_marked_deleted
from miles_core.tenant import TenantContext
from miles_portal.tenant.hooks.models import HookScope, HookTrigger
from miles_portal.tenant.hooks.services.runner import HookRunner
from miles_portal.tenant.tools.builtin_registry import SKILL_BOUND_SLUGS
from miles_portal.tenant.tools.confirmation import ToolConfirmationRequired, ToolSource, resolve_tool_meta
from miles_portal.tenant.tools.invocation_log import write_tool_invocation_log
from miles_portal.tenant.tools.invoke.builtin import invoke_builtin
from miles_portal.tenant.tools.invoke.custom import invoke_custom_http, invoke_custom_script
from miles_portal.tenant.tools.models import Tool, ToolType


async def resolve_bound_skill_ids_from_agent(
    db: AsyncSession,
    agent_id: UUID | None,
) -> list[UUID]:
    """从智能体 config 解析绑定的技能包 ID 列表（``skill_ids`` + 旧 ``skill_package_id``）。

    非 UUID 项跳过 —— 与其它 config 绑定字段同一策略：容忍脏数据，合法项照常生效。
    """
    if not agent_id:
        return []
    from miles_core.models.agent import Agent
    from miles_integrations.langchain.toolkit.catalog import bound_skill_ids

    agent = await db.get(Agent, agent_id)
    if not agent:
        return []
    out: list[UUID] = []
    for raw in bound_skill_ids(agent.config):
        try:
            out.append(UUID(raw))
        except ValueError:
            # 静默可接受：agent.config 中非 UUID 的绑定项无法用于查库，跳过。
            continue
    return out


async def invoke_tool_by_name(
    db: AsyncSession,
    ctx: TenantContext,
    name: str,
    params: dict,
    *,
    source: ToolSource,
    tool_id: UUID | None = None,
    bound_skill_ids: list[UUID] | None = None,
    actor_user_id: UUID | None = None,
    agent_id: UUID | None = None,
) -> dict:
    """按 ``source`` 执行；不含确认与日志（内部用）。

    ``source`` 必须来自 ``resolve_tool_meta`` 的判定结果——本函数**不再**从 slug 形状
    反推种类，避免与审计日志的 ``source`` 出自两套判据。未知取值直接报错（不回落到
    自定义工具，否则判据分歧会被静默吞掉）。
    """
    if source == "mcp":
        from miles_portal.tenant.tools.services.mcp_tools import invoke_mcp_tool_by_slug

        return await invoke_mcp_tool_by_slug(db, ctx, name, params)

    if source == "builtin":
        return await invoke_builtin(
            name,
            params,
            db=db,
            ctx=ctx,
            bound_skill_ids=bound_skill_ids,
            actor_user_id=actor_user_id,
            agent_id=agent_id,
        )

    if source != "custom":
        raise BadRequestError(f"未知的工具种类: {source}")

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
    meta: dict | None = None,
) -> dict:
    """带确认策略、Hook 与审计日志的工具调用入口。

    链路：resolve_tool_meta → 确认校验 → BEFORE_TOOL Hook → invoke_tool_by_name
    → 写 invocation_log → AFTER_TOOL Hook。

    ``meta``：调用方已解析的元数据（``resolve_tool_meta`` 的结果）。传入即复用它，
    否则在本函数内解析——用于「调用方本就需要 ``source`` 做展示」的场景（如试调用 API），
    避免同一次调用把判据跑两遍、并保证审计 ``source`` 与执行分支取自同一份判定。

    确认门槛有两道：工具元数据声明需要确认，以及生图工具的策略判定（如需选择
    参考图）；两道都以 ``halt_for_confirmation`` 收尾（写 ``confirmation_required``
    日志后抛 ``ToolConfirmationRequired``）。审计日志经 ``log_invocation`` 写入，
    以统一 ``tenant_id`` / ``tool_id`` / ``source`` / ``trace_id`` 等身份字段。
    """
    if meta is None:
        meta = await resolve_tool_meta(db, ctx, name, tool_id=tool_id)
    slug = meta["slug"]
    resolved_tool_id = meta.get("tool_id") or tool_id
    tool_params = dict(params)
    # 请求级 trace_id；本次调用的所有日志行共用同一个（不再逐次获取）
    trace_id = get_trace_id()

    async def log_invocation(
        *,
        status: str,
        params: dict,
        latency_ms: int = 0,
        output: dict | None = None,
        error_message: str | None = None,
    ) -> None:
        """写入本次调用的审计日志。

        db / tenant_id / tool_slug / tool_id / source / actor_user_id / agent_id /
        invoke_source / trace_id 对四条路径都相同，故在此固化；调用处只传随分支
        变化的字段（status / params / output / latency_ms / error_message）。
        """
        await write_tool_invocation_log(
            db,
            tenant_id=ctx.tenant_id,
            tool_slug=slug,
            tool_id=resolved_tool_id,
            source=meta["source"],
            status=status,
            params=params,
            output=output,
            latency_ms=latency_ms,
            error_message=error_message,
            actor_user_id=actor_user_id,
            agent_id=agent_id,
            invoke_source=invoke_source,
            trace_id=trace_id,
        )

    async def halt_for_confirmation(description: str | None) -> None:
        """记录待确认日志并抛出确认信号（两道确认门槛共用）。"""
        await log_invocation(status="confirmation_required", params=tool_params)
        raise ToolConfirmationRequired(slug, meta["name"], description, tool_params)

    # 生图：输入区张数覆盖 LLM 参数（须在确认门槛前生效）
    if slug == "generate_image":
        from miles_integrations.generative.request_prefs import resolve_image_n

        tool_params["n"] = resolve_image_n(tool_params.get("n"))

    if meta["require_confirmation"] and not confirmed:
        await halt_for_confirmation(meta.get("description"))

    if slug == "generate_image":
        from miles_integrations.generative.policy import (
            image_tool_confirmation_message,
            needs_image_tool_confirmation,
        )

        if needs_image_tool_confirmation(tool_params) and not confirmed:
            await halt_for_confirmation(image_tool_confirmation_message(tool_params))

    bound_skill_ids: list[UUID] | None = None
    if slug in SKILL_BOUND_SLUGS:
        bound_skill_ids = await resolve_bound_skill_ids_from_agent(db, agent_id)
        if not bound_skill_ids:
            raise BadRequestError("该工具需要智能体绑定技能包（config.skill_ids）")

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
            source=meta["source"],
            tool_id=resolved_tool_id,
            bound_skill_ids=bound_skill_ids,
            actor_user_id=actor_user_id or ctx.user_id,
            agent_id=agent_id,
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        await log_invocation(status="success", params=tool_params, output=output, latency_ms=latency_ms)
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
        # 错误路径记录调用方原始 params（而非 Hook 改写后的），便于回溯用户实际意图
        await log_invocation(
            status="error",
            params=params,
            latency_ms=latency_ms,
            error_message=str(exc)[:2000],
        )
        raise
