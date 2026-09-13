"""画布平台工具执行回调工厂（L1）。

``build_flow_tool_invoker`` 构造 ``RunContext.invoke_platform_tool`` 回调：内部
把执行时 ctx 转 ``TenantContext``、开短会话并委托 ``invoke_tool_with_context``
（确认策略、Hook、调用日志）。原 ``flow_runtime/nodes/tool_nodes.py`` 内联执行
逻辑上移本模块，L3 节点只保留参数合并与调度。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from miles_ai.flow_runtime.types import RunContext
from miles_core.infra.db import AsyncSessionLocal
from miles_core.tenant import TenantContext
from miles_portal.tenant.tools.invoke import invoke_tool_with_context


def build_flow_tool_invoker() -> Callable[..., Awaitable[dict[str, Any]]]:
    """构造画布工具执行回调：``(slug, params, ctx, *, confirmed) -> output``。"""

    async def _invoke(
        slug: str,
        params: dict[str, Any],
        ctx: RunContext,
        *,
        confirmed: bool,
    ) -> dict[str, Any]:
        uid = UUID(ctx.user_id) if ctx.user_id else UUID(int=0)
        tenant_ctx = TenantContext(
            user_id=uid,
            tenant_id=UUID(ctx.tenant_id),
            username="flow",
            is_superuser=ctx.is_superuser,
            permissions=ctx.permissions,
        )
        agent_id = UUID(ctx.agent_id) if ctx.agent_id else None
        async with AsyncSessionLocal() as db:
            return await invoke_tool_with_context(
                db,
                tenant_ctx,
                slug,
                params,
                confirmed=confirmed,
                actor_user_id=tenant_ctx.user_id,
                agent_id=agent_id,
                invoke_source="flow",
            )

    return _invoke
