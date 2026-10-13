"""智能体外部 API 访问（调试 Token / API Key）。"""

from uuid import UUID

from fastapi import Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.response import ok
from miles_common.schema import ApiResponse
from miles_core.deps import require_permissions
from miles_core.infra.db import get_db
from miles_core.tenant import TenantContext
from miles_portal.tenant.agents.schemas.api_access import (
    AgentApiKeyCreate,
    AgentApiKeyCreatedOut,
    AgentApiKeyOut,
    AgentDebugTokenOut,
)
from miles_portal.tenant.agents.views.agents.deps import api_access_svc
from miles_portal.tenant.agents.views.agents.router import router


@router.post(
    "/{agent_id}/api-access/debug-token",
    response_model=ApiResponse[AgentDebugTokenOut],
)
async def create_agent_debug_token(
    agent_id: UUID,
    request: Request,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    """签发短期调试 access JWT，供外部脚本调用 POST …/chat。"""
    ua = request.headers.get("user-agent")
    out = await api_access_svc(db, ctx).create_debug_token(
        agent_id,
        user_agent=f"agent-api-debug;{ua}" if ua else "agent-api-debug",
        ip=request.client.host if request.client else None,
    )
    return ok(out)


@router.get(
    "/{agent_id}/api-access/keys",
    response_model=ApiResponse[list[AgentApiKeyOut]],
)
async def list_agent_api_keys(
    agent_id: UUID,
    include_revoked: bool = Query(False, description="是否包含已吊销密钥"),
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await api_access_svc(db, ctx).list_api_keys(agent_id, include_revoked=include_revoked))


@router.post(
    "/{agent_id}/api-access/keys",
    response_model=ApiResponse[AgentApiKeyCreatedOut],
)
async def create_agent_api_key(
    agent_id: UUID,
    body: AgentApiKeyCreate,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await api_access_svc(db, ctx).create_api_key(agent_id, body))


@router.post(
    "/{agent_id}/api-access/keys/{key_id}/revoke",
    response_model=ApiResponse[AgentApiKeyOut],
)
async def revoke_agent_api_key(
    agent_id: UUID,
    key_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await api_access_svc(db, ctx).revoke_api_key(agent_id, key_id))
