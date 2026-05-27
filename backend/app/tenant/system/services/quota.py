"""租户资源配额：只读汇总与创建前校验。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import ForbiddenError
from app.core.soft_delete import not_deleted
from app.integrations.generative.quota import (
    count_generative_today,
    get_generative_daily_limit,
)
from app.models.agent import Agent
from app.models.flow import Flow
from app.models.tenant import Tenant
from app.tenant.kb.services.quota import (
    assert_can_create_kb,
    assert_can_upload_bytes,
    count_knowledge_bases,
    get_kb_quota_out,
    sum_storage_bytes,
)
from app.tenant.system.schemas.quota import QuotaMetricOut, TenantQuotaOut


def _metric(used: int, max_val: int, *, unit: str = "") -> QuotaMetricOut:
    return QuotaMetricOut(used=used, max=max_val, unit=unit)


async def _load_tenant(db: AsyncSession, tenant_id: UUID) -> Tenant:
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise ForbiddenError("租户不存在")
    return tenant


async def count_agents(db: AsyncSession, tenant_id: UUID) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(Agent)
            .where(Agent.tenant_id == tenant_id, not_deleted(Agent))
        )
        or 0
    )


async def count_flows(db: AsyncSession, tenant_id: UUID) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(Flow)
            .where(Flow.tenant_id == tenant_id, not_deleted(Flow))
        )
        or 0
    )


async def assert_can_create_agent(db: AsyncSession, tenant_id: UUID) -> None:
    tenant = await _load_tenant(db, tenant_id)
    count = await count_agents(db, tenant_id)
    if count >= tenant.max_agents:
        raise ForbiddenError(
            f"智能体数量已达上限（{tenant.max_agents}），请联系平台管理员提升配额"
        )


async def assert_can_create_flow(db: AsyncSession, tenant_id: UUID) -> None:
    tenant = await _load_tenant(db, tenant_id)
    count = await count_flows(db, tenant_id)
    if count >= tenant.max_flows:
        raise ForbiddenError(
            f"流程数量已达上限（{tenant.max_flows}），请联系平台管理员提升配额"
        )


async def get_tenant_quota_out(db: AsyncSession, tenant_id: UUID) -> TenantQuotaOut:
    tenant = await _load_tenant(db, tenant_id)
    kb = await get_kb_quota_out(db, tenant_id)
    used_agents = await count_agents(db, tenant_id)
    used_flows = await count_flows(db, tenant_id)
    gen_limit = await get_generative_daily_limit(db)
    gen_used = await count_generative_today(db, tenant_id)

    return TenantQuotaOut(
        knowledge_bases=_metric(kb["used_knowledge_bases"], kb["max_knowledge_bases"]),
        storage_mb=_metric(kb["used_storage_mb"], kb["max_storage_mb"], unit="MB"),
        agents=_metric(used_agents, tenant.max_agents),
        flows=_metric(used_flows, tenant.max_flows),
        tokens_monthly=_metric(int(tenant.tokens_used_month), int(tenant.max_tokens_monthly)),
        generative_daily=_metric(gen_used, gen_limit, unit="次/日"),
    )


__all__ = [
    "assert_can_create_agent",
    "assert_can_create_flow",
    "get_tenant_quota_out",
]
