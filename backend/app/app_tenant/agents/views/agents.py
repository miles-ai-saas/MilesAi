from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.app_tenant.agents.schemas.agent import AgentCreate, AgentOut, AgentUpdate, ChatRequest, ChatResponse
from app.common.schema import ApiResponse, PageParams, PageResult
from app.app_tenant.agents.services.agent import AgentService

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> AgentService:
    return AgentService(db, ctx)


@router.get("", response_model=ApiResponse[PageResult[AgentOut]])
async def list_agents(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_agents(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[AgentOut])
async def create_agent(
    body: AgentCreate,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).create_agent(body))


@router.get("/{agent_id}", response_model=ApiResponse[AgentOut])
async def get_agent(
    agent_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_agent(agent_id))


@router.patch("/{agent_id}", response_model=ApiResponse[AgentOut])
async def update_agent(
    agent_id: UUID,
    body: AgentUpdate,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).update_agent(agent_id, body))


@router.delete("/{agent_id}", response_model=ApiResponse[None])
async def delete_agent(
    agent_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db, ctx).delete_agent(agent_id)
    return ok(message="已删除")


@router.post("/{agent_id}/chat", response_model=ApiResponse[ChatResponse])
async def chat_agent(
    agent_id: UUID,
    body: ChatRequest,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).chat(agent_id, body))
