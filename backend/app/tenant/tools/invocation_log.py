"""工具调用日志写入。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant.tools.models import ToolInvocationLog


async def write_tool_invocation_log(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    tool_slug: str,
    source: str,
    status: str,
    params: dict,
    latency_ms: int = 0,
    tool_id: UUID | None = None,
    output: dict | None = None,
    error_message: str | None = None,
    actor_user_id: UUID | None = None,
    agent_id: UUID | None = None,
    invoke_source: str = "api",
    trace_id: str | None = None,
) -> None:
    row = ToolInvocationLog(
        tenant_id=tenant_id,
        tool_slug=tool_slug,
        tool_id=tool_id,
        source=source,
        status=status,
        params=params,
        output=output,
        error_message=error_message,
        latency_ms=latency_ms,
        actor_user_id=actor_user_id,
        agent_id=agent_id,
        invoke_source=invoke_source,
        trace_id=trace_id,
    )
    db.add(row)
    await db.flush()
