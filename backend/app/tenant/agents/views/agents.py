"""
智能体 HTTP API。

``POST /{id}/chat`` 委托 ``AgentService.chat``，内部按 A2A/子 Agent/流程/RAG 优先级编排；
知识库检索细节见 ``tenant.agents.services.agent._rag_chat`` 与 ``integrations.langgraph``。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.tenant.agents.schemas.agent import AgentCreate, AgentOut, AgentUpdate, ChatRequest, ChatResponse
from app.common.schema import ApiResponse, PageParams, PageResult
from app.tenant.agents.services.agent import AgentService
from app.models.agent import AgentType

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> AgentService:
    return AgentService(db, ctx)


@router.get("", response_model=ApiResponse[PageResult[AgentOut]])
async def list_agents(
    params: PageParams = Depends(get_page_params),
    agent_type: AgentType | None = Query(None, description="按类型筛选：custom | a2a"),
    category_id: UUID | None = Query(None, description="按分类 ID 筛选"),
    tag_ids: list[UUID] | None = Query(None, description="按标签筛选（任一匹配）"),
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_agents(
        params, agent_type=agent_type, category_id=category_id, tag_ids=tag_ids
    )
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
    """主对话入口：合规 → 钩子 → A2A/子 Agent/流程/RAG 路由（见 AgentService.chat）。"""
    return ok(await _svc(db, ctx).chat(agent_id, body))
