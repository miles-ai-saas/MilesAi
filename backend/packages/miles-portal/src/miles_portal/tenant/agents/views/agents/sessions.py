"""智能体对话会话。"""

from uuid import UUID

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.response import ok, page_ok
from miles_common.schema import ApiResponse, PageParams, PageResult
from miles_core.deps import get_page_params, require_permissions
from miles_core.infra.db import get_db
from miles_core.tenant import TenantContext
from miles_portal.tenant.agents.schemas.chat_sessions import (
    ChatSessionCreate,
    ChatSessionDetailOut,
    ChatSessionOut,
    ChatSessionUpdate,
)
from miles_portal.tenant.agents.views.agents.deps import chat_session_svc
from miles_portal.tenant.agents.views.agents.router import router


@router.get("/{agent_id}/chat-sessions", response_model=ApiResponse[PageResult[ChatSessionOut]])
async def list_agent_chat_sessions(
    agent_id: UUID,
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await chat_session_svc(db, ctx).list_sessions(agent_id, params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/{agent_id}/chat-sessions", response_model=ApiResponse[ChatSessionOut])
async def create_agent_chat_session(
    agent_id: UUID,
    body: ChatSessionCreate,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await chat_session_svc(db, ctx).create_session(agent_id, body))


@router.get("/{agent_id}/chat-sessions/{session_id}", response_model=ApiResponse[ChatSessionDetailOut])
async def get_agent_chat_session(
    agent_id: UUID,
    session_id: str,
    before_sort_index: int | None = Query(None, description="游标：获取 sort_index 小于此值的更早消息"),
    limit: int = Query(10, ge=1, le=100, description="返回消息数量，默认 10"),
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(
        await chat_session_svc(db, ctx).get_session(
            agent_id,
            session_id,
            before_sort_index=before_sort_index,
            limit=limit,
        )
    )


@router.patch("/{agent_id}/chat-sessions/{session_id}", response_model=ApiResponse[ChatSessionOut])
async def update_agent_chat_session(
    agent_id: UUID,
    session_id: str,
    body: ChatSessionUpdate,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await chat_session_svc(db, ctx).update_session(agent_id, session_id, body))


@router.delete("/{agent_id}/chat-sessions/{session_id}", response_model=ApiResponse[None])
async def delete_agent_chat_session(
    agent_id: UUID,
    session_id: str,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    await chat_session_svc(db, ctx).delete_session(agent_id, session_id)
    return ok(message="已删除")
