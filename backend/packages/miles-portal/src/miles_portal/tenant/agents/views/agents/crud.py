"""智能体 CRUD、导入导出、统计与架构预览。"""

from uuid import UUID

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.response import ok, page_ok
from miles_common.schema import ApiResponse, PageParams, PageResult
from miles_core.deps import get_page_params, require_permissions
from miles_core.infra.db import get_db
from miles_core.tenant import TenantContext
from miles_portal.tenant.agents.schemas.agent import AgentCreate, AgentOut, AgentPackage, AgentUpdate
from miles_portal.tenant.agents.schemas.architecture import AgentArchitectureOut
from miles_portal.tenant.agents.schemas.enums import AgentType
from miles_portal.tenant.agents.schemas.meta import AgentMetaOut
from miles_portal.tenant.agents.schemas.stats import AgentStatsOut
from miles_portal.tenant.agents.views.agents.deps import agent_svc, arch_svc, stats_svc
from miles_portal.tenant.agents.views.agents.router import router


# GET */meta：枚举展示字典，须在 /{id} 等路径参数路由之前注册
@router.get("/meta", response_model=ApiResponse[AgentMetaOut])
async def agents_meta(
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await agent_svc(db, ctx).get_meta())


@router.get("", response_model=ApiResponse[PageResult[AgentOut]])
async def list_agents(
    params: PageParams = Depends(get_page_params),
    agent_type: AgentType | None = Query(None, description="按类型筛选：custom | a2a"),
    category_id: UUID | None = Query(None, description="按分类 ID 筛选"),
    tag_ids: list[UUID] | None = Query(None, description="按标签筛选（任一匹配）"),
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await agent_svc(db, ctx).list_agents(
        params, agent_type=agent_type, category_id=category_id, tag_ids=tag_ids
    )
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[AgentOut])
async def create_agent(
    body: AgentCreate,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await agent_svc(db, ctx).create_agent(body))


@router.post("/import", response_model=ApiResponse[AgentOut])
async def import_agent(
    body: AgentPackage,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    """从 JSON 包导入智能体。"""
    agent = await agent_svc(db, ctx).import_package(body)
    return ok(agent)


@router.get("/{agent_id}", response_model=ApiResponse[AgentOut])
async def get_agent(
    agent_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await agent_svc(db, ctx).get_agent(agent_id))


@router.patch("/{agent_id}", response_model=ApiResponse[AgentOut])
async def update_agent(
    agent_id: UUID,
    body: AgentUpdate,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await agent_svc(db, ctx).update_agent(agent_id, body))


@router.delete("/{agent_id}", response_model=ApiResponse[None])
async def delete_agent(
    agent_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    await agent_svc(db, ctx).delete_agent(agent_id)
    return ok(message="已删除")


@router.get("/{agent_id}/stats", response_model=ApiResponse[AgentStatsOut])
async def agent_stats(
    agent_id: UUID,
    days: int = Query(7, ge=3, le=90, description="统计天数：3/7/15/30/90"),
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await stats_svc(db, ctx).overview(agent_id, days=days))


@router.get("/{agent_id}/architecture", response_model=ApiResponse[AgentArchitectureOut])
async def agent_architecture(
    agent_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    """对话执行路径与编排预览（路由与 ``AgentService.chat`` 一致）。"""
    return ok(await arch_svc(db, ctx).overview(agent_id))


@router.get("/{agent_id}/export", response_model=ApiResponse[AgentPackage])
async def export_agent(
    agent_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    """导出智能体配置为 JSON 包（可跨租户导入）。"""
    pkg = await agent_svc(db, ctx).export_package(agent_id)
    return ok(pkg)
