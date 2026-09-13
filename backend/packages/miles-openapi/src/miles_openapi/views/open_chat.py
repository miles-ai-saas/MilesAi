"""开放调用：仅 X-API-Key 的智能体对话入口。"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.response import ok
from miles_common.schema import ApiResponse
from miles_core.infra.db import get_db
from miles_core.tenant import TenantContext
from miles_portal.tenant.agents.deps_api_auth import require_agent_api_key
from miles_portal.tenant.agents.schemas.agent import ChatRequest, ChatResponse
from miles_portal.tenant.agents.services.agent import AgentService

router = APIRouter()


@router.post("/agents/{agent_id}/chat", response_model=ApiResponse[ChatResponse])
async def open_agent_chat(
    agent_id: UUID,
    body: ChatRequest,
    ctx: TenantContext = Depends(require_agent_api_key),
    db: AsyncSession = Depends(get_db),
):
    """对外主推对话入口；鉴权仅接受 X-API-Key。"""
    return ok(await AgentService(db, ctx).chat(agent_id, body))
