"""智能体统计：按日时间轴；待会话/消息持久化后在此聚合。"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundError
from app.core.service import BaseService
from app.core.soft_delete import is_marked_deleted
from app.core.tenant import TenantContext, assert_tenant_access
from app.tenant.agents.repositories.agent import AgentRepository
from app.tenant.agents.schemas.stats import AgentStatsOut, AgentStatsPoint

ALLOWED_DAYS = (3, 7, 15, 30, 90)


def _normalize_days(days: int) -> int:
    if days in ALLOWED_DAYS:
        return days
    return 7 if days <= 7 else min(max(days, 3), 90)


def _day_range(days: int) -> list[str]:
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days - 1)
    out: list[str] = []
    cur = start
    while cur <= end:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def _zero_series(days: int) -> list[AgentStatsPoint]:
    return [AgentStatsPoint(date=d, value=0) for d in _day_range(days)]


class AgentStatsService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self._repo = AgentRepository(db)

    async def _ensure_agent(self, agent_id: UUID) -> None:
        agent = await self._repo.get_detail(agent_id)
        if not agent or is_marked_deleted(agent):
            raise NotFoundError("智能体不存在")
        assert_tenant_access(self.ctx, agent.tenant_id)

    async def overview(self, agent_id: UUID, *, days: int) -> AgentStatsOut:
        await self._ensure_agent(agent_id)
        n = _normalize_days(days)
        series = _zero_series(n)
        return AgentStatsOut(
            days=n,
            sessions_total=0,
            active_users_total=0,
            messages_total=0,
            avg_rounds_total=0,
            sessions_by_day=series,
            active_users_by_day=series,
            messages_by_day=series,
            avg_rounds_by_day=series,
        )
