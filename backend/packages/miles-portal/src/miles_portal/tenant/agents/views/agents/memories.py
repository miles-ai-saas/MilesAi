"""智能体跨会话用户记忆。"""

from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.response import ok
from miles_common.schema import ApiResponse
from miles_core.deps import require_permissions
from miles_core.infra.db import get_db
from miles_core.tenant import TenantContext
from miles_portal.tenant.agents.schemas.user_memory import UserMemoryItemOut, UserMemoryListOut
from miles_portal.tenant.agents.views.agents.deps import user_memory_svc
from miles_portal.tenant.agents.views.agents.router import router


@router.get("/{agent_id}/user-memories", response_model=ApiResponse[UserMemoryListOut])
async def list_agent_user_memories(
    agent_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    """当前登录用户在该智能体下的跨会话记忆（summary / preference）。"""
    return ok(await user_memory_svc(db, ctx).list_mine(agent_id))


@router.get("/{agent_id}/user-memories/{kind}", response_model=ApiResponse[UserMemoryItemOut])
async def get_agent_user_memory(
    agent_id: UUID,
    kind: str,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await user_memory_svc(db, ctx).get_mine(agent_id, kind))


@router.delete("/{agent_id}/user-memories", response_model=ApiResponse[dict])
async def clear_agent_user_memories(
    agent_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    """一键清空当前用户在该智能体下的全部长期记忆。"""
    deleted = await user_memory_svc(db, ctx).clear_mine(agent_id)
    return ok({"deleted": deleted}, message="已清空")
