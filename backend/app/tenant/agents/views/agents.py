"""
智能体 HTTP API。

``POST /{id}/chat`` 委托 ``AgentService.chat``，内部按 A2A/子 Agent/流程/RAG 优先级编排；
知识库检索细节见 ``tenant.agents.services.agent`` 子包 ``rag_chat`` 与 ``integrations.langgraph``。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.tenant.agents.schemas.agent import AgentCreate, AgentOut, AgentPackage, AgentUpdate, ChatRequest, ChatResponse
from app.tenant.agents.schemas.meta import AgentMetaOut
from app.tenant.agents.schemas.architecture import AgentArchitectureOut
from app.tenant.agents.schemas.call_records import AgentCallRecordDetailOut, AgentCallRecordOut
from app.tenant.agents.schemas.chat_sessions import ChatSessionCreate, ChatSessionDetailOut, ChatSessionOut, ChatSessionUpdate
from app.tenant.agents.schemas.schedule import AgentScheduleCreate, AgentScheduleOut, AgentScheduleUpdate
from app.tenant.agents.schemas.schedule_run import AgentScheduleRunOut
from app.tenant.agents.schemas.stats import AgentStatsOut
from app.common.schema import ApiResponse, PageParams, PageResult
from app.tenant.agents.services.agent import AgentService
from app.tenant.agents.services.call_records import AgentCallRecordService, parse_call_record_datetime
from app.tenant.agents.services.chat_sessions import AgentChatSessionService
from app.tenant.agents.ws import agent_chat_ws_router
from app.tenant.agents.services.architecture import AgentArchitectureService
from app.tenant.agents.services.schedule import AgentScheduleService
from app.tenant.agents.services.stats import AgentStatsService
from app.models.agent import AgentType

router = APIRouter()
router.include_router(agent_chat_ws_router)


def _svc(db: AsyncSession, ctx: TenantContext) -> AgentService:
    return AgentService(db, ctx)


def _stats_svc(db: AsyncSession, ctx: TenantContext) -> AgentStatsService:
    return AgentStatsService(db, ctx)


def _arch_svc(db: AsyncSession, ctx: TenantContext) -> AgentArchitectureService:
    return AgentArchitectureService(db, ctx)


def _schedule_svc(db: AsyncSession, ctx: TenantContext) -> AgentScheduleService:
    return AgentScheduleService(db, ctx)


def _call_record_svc(db: AsyncSession, ctx: TenantContext) -> AgentCallRecordService:
    return AgentCallRecordService(db, ctx)


def _chat_session_svc(db: AsyncSession, ctx: TenantContext) -> AgentChatSessionService:
    return AgentChatSessionService(db, ctx)


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
    result = await _svc(db, ctx).list_agents(params, agent_type=agent_type, category_id=category_id, tag_ids=tag_ids)
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


@router.get("/{agent_id}/call-records", response_model=ApiResponse[PageResult[AgentCallRecordOut]])
async def list_agent_call_records(
    agent_id: UUID,
    params: PageParams = Depends(get_page_params),
    status: str | None = Query(None, description="success | failed | blocked"),
    conversation_id: str | None = Query(None, max_length=128),
    route: str | None = Query(None, max_length=32),
    q: str | None = Query(None, max_length=128, description="搜索问题摘要或 trace_id"),
    from_dt: str | None = Query(None, alias="from", description="起始时间 ISO8601 或 YYYY-MM-DD"),
    to_dt: str | None = Query(None, alias="to", description="结束时间 ISO8601 或 YYYY-MM-DD"),
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _call_record_svc(db, ctx).list_records(
        agent_id,
        params,
        status=status,
        conversation_id=conversation_id,
        route=route,
        q=q,
        from_dt=parse_call_record_datetime(from_dt),
        to_dt=parse_call_record_datetime(to_dt),
    )
    return page_ok(result.items, result.total, result.page, result.size)


@router.get("/{agent_id}/call-records/{call_id}", response_model=ApiResponse[AgentCallRecordDetailOut])
async def get_agent_call_record(
    agent_id: UUID,
    call_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _call_record_svc(db, ctx).get_record(agent_id, call_id))


@router.get("/{agent_id}/chat-sessions", response_model=ApiResponse[PageResult[ChatSessionOut]])
async def list_agent_chat_sessions(
    agent_id: UUID,
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _chat_session_svc(db, ctx).list_sessions(agent_id, params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/{agent_id}/chat-sessions", response_model=ApiResponse[ChatSessionOut])
async def create_agent_chat_session(
    agent_id: UUID,
    body: ChatSessionCreate,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _chat_session_svc(db, ctx).create_session(agent_id, body))


@router.get("/{agent_id}/chat-sessions/{session_id}", response_model=ApiResponse[ChatSessionDetailOut])
async def get_agent_chat_session(
    agent_id: UUID,
    session_id: str,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _chat_session_svc(db, ctx).get_session(agent_id, session_id))


@router.patch("/{agent_id}/chat-sessions/{session_id}", response_model=ApiResponse[ChatSessionOut])
async def update_agent_chat_session(
    agent_id: UUID,
    session_id: str,
    body: ChatSessionUpdate,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _chat_session_svc(db, ctx).update_session(agent_id, session_id, body))


@router.delete("/{agent_id}/chat-sessions/{session_id}", response_model=ApiResponse[None])
async def delete_agent_chat_session(
    agent_id: UUID,
    session_id: str,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    await _chat_session_svc(db, ctx).delete_session(agent_id, session_id)
    return ok(message="已删除")


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


@router.get(
    "/{agent_id}/schedules/{schedule_id}/runs",
    response_model=ApiResponse[PageResult[AgentScheduleRunOut]],
)
async def list_agent_schedule_runs(
    agent_id: UUID,
    schedule_id: UUID,
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _schedule_svc(db, ctx).list_runs(agent_id, schedule_id, params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/{agent_id}/chat", response_model=ApiResponse[ChatResponse])
async def chat_agent(
    agent_id: UUID,
    body: ChatRequest,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    """主对话入口：合规 → 钩子 → A2A/子 Agent/流程/RAG 路由（见 AgentService.chat）。"""
    return ok(await _svc(db, ctx).chat(agent_id, body))


@router.get("/{agent_id}/export", response_model=ApiResponse[AgentPackage])
async def export_agent(
    agent_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    """导出智能体配置为 JSON 包（可跨租户导入）。"""
    pkg = await _svc(db, ctx).export_package(agent_id)
    return ok(pkg)


@router.post("/import", response_model=ApiResponse[AgentOut])
async def import_agent(
    body: AgentPackage,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    """从 JSON 包导入智能体。"""
    agent = await _svc(db, ctx).import_package(body)
    return ok(agent)
