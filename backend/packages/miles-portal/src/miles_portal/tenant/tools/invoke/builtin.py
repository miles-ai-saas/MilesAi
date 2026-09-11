"""内置工具分发：``BUILTIN_HANDLERS`` 查表，由 ``invoke/__init__.py`` 对外暴露 ``invoke_builtin``。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError
from miles_core.tenant import TenantContext
from miles_portal.tenant.tools.builtins.handlers import BUILTIN_HANDLERS


async def invoke_builtin(
    name: str,
    params: dict,
    *,
    db: AsyncSession,
    ctx: TenantContext,
    bound_skill_id: UUID | None = None,
    actor_user_id: UUID | None = None,
    agent_id: UUID | None = None,
) -> dict:
    """按内置 slug 分发至 ``builtins.handlers``。"""
    handler = BUILTIN_HANDLERS.get(name)
    if handler is None:
        raise BadRequestError(f"未知内置工具: {name}")
    return await handler(
        params,
        db=db,
        ctx=ctx,
        bound_skill_id=bound_skill_id,
        actor_user_id=actor_user_id,
        agent_id=agent_id,
    )
