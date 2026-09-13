"""智能体统计：从 agt_agent_chat_calls 按日聚合。"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import NotFoundError
from miles_core.models.agent.chat_call import AgentChatCall
from miles_core.service import BaseService
from miles_core.soft_delete import is_marked_deleted
from miles_core.tenant import TenantContext, assert_tenant_access, tenant_filters
from miles_portal.tenant.agents.repositories.agent import AgentRepository
from miles_portal.tenant.agents.schemas.stats import AgentStatsOut, AgentStatsPoint

ALLOWED_DAYS = (3, 7, 15, 30, 90)


def _normalize_days(days: int) -> int:
    if days in ALLOWED_DAYS:
        return days
    return 7 if days <= 7 else min(max(days, 3), 90)


def _day_range(days: int) -> list[str]:
    end = datetime.now(UTC).date()
    start = end - timedelta(days=days - 1)
    out: list[str] = []
    cur = start
    while cur <= end:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def _series_from_map(day_labels: list[str], values: dict[str, float | int]) -> list[AgentStatsPoint]:
    return [AgentStatsPoint(date=d, value=float(values.get(d, 0))) for d in day_labels]


def _avg_rounds(messages: int, sessions: int) -> float:
    if sessions <= 0:
        return 0.0
    return round(messages / sessions, 1)


class AgentStatsService(BaseService):
    """智能体使用统计服务，按日聚合对话调用记录。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self._repo = AgentRepository(db)

    async def _ensure_agent(self, agent_id: UUID) -> None:
        agent = await self._repo.get_detail(agent_id)
        if not agent or is_marked_deleted(agent):
            raise NotFoundError("智能体不存在")
        assert_tenant_access(self.ctx, agent.tenant_id)

    def _window_bounds(self, days: int) -> tuple[list[str], datetime, datetime]:
        labels = _day_range(days)
        start_date = datetime.strptime(labels[0], "%Y-%m-%d").date()
        end_date = datetime.strptime(labels[-1], "%Y-%m-%d").date()
        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
        end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
        return labels, start_dt, end_dt

    async def overview(self, agent_id: UUID, *, days: int) -> AgentStatsOut:
        """返回指定窗口内的总量与按日序列；``days`` 会先夹取到允许值。"""
        await self._ensure_agent(agent_id)
        n = _normalize_days(days)
        day_labels, start_dt, end_dt = self._window_bounds(n)
        base_filters = tenant_filters(self.ctx, AgentChatCall.tenant_id) + [
            AgentChatCall.agent_id == agent_id,
            AgentChatCall.created_at >= start_dt,
            AgentChatCall.created_at < end_dt,
        ]
        session_filters = base_filters + [
            AgentChatCall.conversation_id.isnot(None),
            AgentChatCall.conversation_id != "",
        ]

        messages_total = int(await self.db.scalar(select(func.count()).select_from(AgentChatCall).where(*base_filters)) or 0)
        sessions_total = int(
            await self.db.scalar(select(func.count(func.distinct(AgentChatCall.conversation_id))).select_from(AgentChatCall).where(*session_filters)) or 0
        )
        active_users_total = int(
            await self.db.scalar(
                select(func.count(func.distinct(AgentChatCall.actor_user_id)))
                .select_from(AgentChatCall)
                .where(*base_filters, AgentChatCall.actor_user_id.isnot(None))
            )
            or 0
        )

        day_col = cast(AgentChatCall.created_at, Date)
        msg_rows = await self.db.execute(select(day_col.label("day"), func.count(AgentChatCall.id)).where(*base_filters).group_by(day_col))
        messages_by_day = {row.day.isoformat(): int(row[1]) for row in msg_rows.all()}

        sess_rows = await self.db.execute(
            select(day_col.label("day"), func.count(func.distinct(AgentChatCall.conversation_id))).where(*session_filters).group_by(day_col)
        )
        sessions_by_day = {row.day.isoformat(): int(row[1]) for row in sess_rows.all()}

        user_rows = await self.db.execute(
            select(day_col.label("day"), func.count(func.distinct(AgentChatCall.actor_user_id)))
            .where(*base_filters, AgentChatCall.actor_user_id.isnot(None))
            .group_by(day_col)
        )
        active_users_by_day = {row.day.isoformat(): int(row[1]) for row in user_rows.all()}

        avg_rounds_by_day = {d: _avg_rounds(int(messages_by_day.get(d, 0)), int(sessions_by_day.get(d, 0))) for d in day_labels}

        return AgentStatsOut(
            days=n,
            sessions_total=sessions_total,
            active_users_total=active_users_total,
            messages_total=messages_total,
            avg_rounds_total=_avg_rounds(messages_total, sessions_total),
            sessions_by_day=_series_from_map(day_labels, sessions_by_day),
            active_users_by_day=_series_from_map(day_labels, active_users_by_day),
            messages_by_day=_series_from_map(day_labels, messages_by_day),
            avg_rounds_by_day=_series_from_map(day_labels, avg_rounds_by_day),
        )
