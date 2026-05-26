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
from app.tenant.agents.schemas.meta import AgentMetaOut
from app.tenant.agents.schemas.architecture import AgentArchitectureOut
from app.tenant.agents.schemas.schedule import AgentScheduleCreate, AgentScheduleOut, AgentScheduleUpdate
from app.tenant.agents.schemas.stats import AgentStatsOut
from app.common.schema import ApiResponse, PageParams, PageResult
from app.tenant.agents.services.agent import AgentService
from app.tenant.agents.services.architecture import AgentArchitectureService
from app.tenant.agents.services.schedule import AgentScheduleService
from app.tenant.agents.services.stats import AgentStatsService
from app.models.agent import AgentType

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> AgentService:
    return AgentService(db, ctx)


def _stats_svc(db: AsyncSession, ctx: TenantContext) -> AgentStatsService:
    return AgentStatsService(db, ctx)


def _arch_svc(db: AsyncSession, ctx: TenantContext) -> AgentArchitectureService:
    return AgentArchitectureService(db, ctx)


def _schedule_svc(db: AsyncSession, ctx: TenantContext) -> AgentScheduleService:
    return AgentScheduleService(db, ctx)


# GET */meta：枚举展示字典，须在 /{id} 等路径参数路由之前注册
@router.get("/meta", response_model=ApiResponse[AgentMetaOut])
async def agents_meta(
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_meta())


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


@router.get("/{agent_id}/stats", response_model=ApiResponse[AgentStatsOut])
async def agent_stats(
    agent_id: UUID,
    days: int = Query(7, ge=3, le=90, description="统计天数：3/7/15/30/90"),
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _stats_svc(db, ctx).overview(agent_id, days=days))


@router.get("/{agent_id}/architecture", response_model=ApiResponse[AgentArchitectureOut])
async def agent_architecture(
    agent_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    """对话执行路径与编排预览（路由与 ``AgentService.chat`` 一致）。"""
    return ok(await _arch_svc(db, ctx).overview(agent_id))


@router.get("/{agent_id}/schedules", response_model=ApiResponse[PageResult[AgentScheduleOut]])
async def list_agent_schedules(
    agent_id: UUID,
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _schedule_svc(db, ctx).list_schedules(agent_id, params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/{agent_id}/schedules", response_model=ApiResponse[AgentScheduleOut])
async def create_agent_schedule(
    agent_id: UUID,
    body: AgentScheduleCreate,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _schedule_svc(db, ctx).create_schedule(agent_id, body))


@router.patch("/{agent_id}/schedules/{schedule_id}", response_model=ApiResponse[AgentScheduleOut])
async def update_agent_schedule(
    agent_id: UUID,
    schedule_id: UUID,
    body: AgentScheduleUpdate,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _schedule_svc(db, ctx).update_schedule(agent_id, schedule_id, body))


@router.delete("/{agent_id}/schedules/{schedule_id}", response_model=ApiResponse[None])
async def delete_agent_schedule(
    agent_id: UUID,
    schedule_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    await _schedule_svc(db, ctx).delete_schedule(agent_id, schedule_id)
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
