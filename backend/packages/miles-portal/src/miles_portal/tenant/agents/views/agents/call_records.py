"""智能体调用记录。"""

from uuid import UUID

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.response import ok, page_ok
from miles_common.schema import ApiResponse, PageParams, PageResult
from miles_core.deps import get_page_params, require_permissions
from miles_core.infra.db import get_db
from miles_core.tenant import TenantContext
from miles_portal.tenant.agents.schemas.call_records import AgentCallRecordDetailOut, AgentCallRecordOut
from miles_portal.tenant.agents.services.call_records import parse_call_record_datetime
from miles_portal.tenant.agents.views.agents.deps import call_record_svc
from miles_portal.tenant.agents.views.agents.router import router


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
    result = await call_record_svc(db, ctx).list_records(
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
    return ok(await call_record_svc(db, ctx).get_record(agent_id, call_id))
