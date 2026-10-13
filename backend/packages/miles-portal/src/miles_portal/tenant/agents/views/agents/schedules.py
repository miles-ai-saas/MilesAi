"""智能体定时调度。"""

from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.response import ok, page_ok
from miles_common.schema import ApiResponse, PageParams, PageResult
from miles_core.deps import get_page_params, require_permissions
from miles_core.infra.db import get_db
from miles_core.tenant import TenantContext
from miles_portal.tenant.agents.schemas.schedule import AgentScheduleCreate, AgentScheduleOut, AgentScheduleUpdate
from miles_portal.tenant.agents.schemas.schedule_run import AgentScheduleRunOut
from miles_portal.tenant.agents.views.agents.deps import schedule_svc
from miles_portal.tenant.agents.views.agents.router import router


@router.get("/{agent_id}/schedules", response_model=ApiResponse[PageResult[AgentScheduleOut]])
async def list_agent_schedules(
    agent_id: UUID,
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await schedule_svc(db, ctx).list_schedules(agent_id, params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/{agent_id}/schedules", response_model=ApiResponse[AgentScheduleOut])
async def create_agent_schedule(
    agent_id: UUID,
    body: AgentScheduleCreate,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await schedule_svc(db, ctx).create_schedule(agent_id, body))


@router.patch("/{agent_id}/schedules/{schedule_id}", response_model=ApiResponse[AgentScheduleOut])
async def update_agent_schedule(
    agent_id: UUID,
    schedule_id: UUID,
    body: AgentScheduleUpdate,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await schedule_svc(db, ctx).update_schedule(agent_id, schedule_id, body))


@router.delete("/{agent_id}/schedules/{schedule_id}", response_model=ApiResponse[None])
async def delete_agent_schedule(
    agent_id: UUID,
    schedule_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    await schedule_svc(db, ctx).delete_schedule(agent_id, schedule_id)
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
    result = await schedule_svc(db, ctx).list_runs(agent_id, schedule_id, params)
    return page_ok(result.items, result.total, result.page, result.size)
