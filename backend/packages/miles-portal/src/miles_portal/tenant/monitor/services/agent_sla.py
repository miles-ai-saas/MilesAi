"""从 agt_agent_chat_calls 聚合 Agent SLA（延迟分位、成功率、Token）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.models.agent import Agent
from miles_core.models.agent.chat_call import AgentChatCall
from miles_core.service import BaseService
from miles_core.tenant import TenantContext, tenant_filters
from miles_portal.tenant.monitor.schemas.agent_sla import (
    AgentSlaAgentRow,
    AgentSlaDailyPoint,
    AgentSlaMetrics,
    AgentSlaReport,
    AgentSlaRouteRow,
)

ALLOWED_DAYS = (3, 7, 15, 30)
TOP_AGENTS = 20


def normalize_sla_days(days: int) -> int:
    if days in ALLOWED_DAYS:
        return days
    return 7 if days <= 7 else min(max(days, 3), 30)


def success_rate(success: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * success / total, 2)


def percentile(sorted_vals: list[int], q: float) -> float:
    """线性插值分位数；空列表返回 0。用于单测与小样本回退。"""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    q = min(1.0, max(0.0, q))
    pos = (len(sorted_vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return round(sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac, 2)


def build_metrics(
    *,
    call_count: int,
    success_count: int,
    failed_count: int,
    blocked_count: int,
    latency_avg_ms: float,
    latency_p50_ms: float,
    latency_p95_ms: float,
    tokens_per_call_avg: float,
    total_tokens: int,
) -> AgentSlaMetrics:
    return AgentSlaMetrics(
        call_count=call_count,
        success_count=success_count,
        failed_count=failed_count,
        blocked_count=blocked_count,
        success_rate=success_rate(success_count, call_count),
        latency_avg_ms=round(float(latency_avg_ms or 0), 2),
        latency_p50_ms=round(float(latency_p50_ms or 0), 2),
        latency_p95_ms=round(float(latency_p95_ms or 0), 2),
        tokens_per_call_avg=round(float(tokens_per_call_avg or 0), 2),
        total_tokens=int(total_tokens or 0),
    )


class AgentSlaService(BaseService):
    """租户级 Agent 对话 SLA 聚合（可选按 agent_id 过滤）。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    def _window_start(self, days: int) -> datetime:
        # 与 monitor trends 一致：含当天在内的近 N 个自然日近似窗口
        return datetime.now(UTC) - timedelta(days=days - 1)

    def _base_filters(self, days: int, agent_id: UUID | None):
        filters = tenant_filters(self.ctx, AgentChatCall.tenant_id)
        filters.append(AgentChatCall.created_at >= self._window_start(days))
        if agent_id is not None:
            filters.append(AgentChatCall.agent_id == agent_id)
        return filters

    @staticmethod
    def _metric_columns():
        token_expr = AgentChatCall.prompt_tokens + AgentChatCall.completion_tokens
        success_c = func.coalesce(func.sum(case((AgentChatCall.status == "success", 1), else_=0)), 0)
        failed_c = func.coalesce(func.sum(case((AgentChatCall.status == "failed", 1), else_=0)), 0)
        blocked_c = func.coalesce(func.sum(case((AgentChatCall.status == "blocked", 1), else_=0)), 0)
        return (
            func.count(AgentChatCall.id).label("call_count"),
            success_c.label("success_count"),
            failed_c.label("failed_count"),
            blocked_c.label("blocked_count"),
            func.coalesce(func.avg(AgentChatCall.latency_ms), 0).label("latency_avg"),
            func.percentile_cont(0.5).within_group(AgentChatCall.latency_ms).label("latency_p50"),
            func.percentile_cont(0.95).within_group(AgentChatCall.latency_ms).label("latency_p95"),
            func.coalesce(func.avg(token_expr), 0).label("tokens_avg"),
            func.coalesce(func.sum(token_expr), 0).label("total_tokens"),
        )

    @staticmethod
    def _row_to_metrics(row) -> AgentSlaMetrics:
        return build_metrics(
            call_count=int(row.call_count or 0),
            success_count=int(row.success_count or 0),
            failed_count=int(row.failed_count or 0),
            blocked_count=int(row.blocked_count or 0),
            latency_avg_ms=float(row.latency_avg or 0),
            latency_p50_ms=float(row.latency_p50 or 0) if row.latency_p50 is not None else 0.0,
            latency_p95_ms=float(row.latency_p95 or 0) if row.latency_p95 is not None else 0.0,
            tokens_per_call_avg=float(row.tokens_avg or 0),
            total_tokens=int(row.total_tokens or 0),
        )

    async def report(self, *, days: int = 7, agent_id: UUID | None = None) -> AgentSlaReport:
        n = normalize_sla_days(days)
        filters = self._base_filters(n, agent_id)
        cols = self._metric_columns()

        overview_row = (await self.db.execute(select(*cols).where(*filters))).one()
        overview = self._row_to_metrics(overview_row)

        route_rows = await self.db.execute(
            select(AgentChatCall.route, *cols).where(*filters).group_by(AgentChatCall.route).order_by(func.count(AgentChatCall.id).desc())
        )
        by_route = [
            AgentSlaRouteRow(route=str(r.route or "unknown"), **self._row_to_metrics(r).model_dump()) for r in route_rows.all()
        ]

        by_agent: list[AgentSlaAgentRow] = []
        if agent_id is None:
            agent_stmt = (
                select(AgentChatCall.agent_id, Agent.name.label("agent_name"), *cols)
                .select_from(AgentChatCall)
                .outerjoin(
                    Agent,
                    (Agent.id == AgentChatCall.agent_id) & (Agent.tenant_id == AgentChatCall.tenant_id),
                )
                .where(*filters)
                .group_by(AgentChatCall.agent_id, Agent.name)
                .order_by(func.count(AgentChatCall.id).desc())
                .limit(TOP_AGENTS)
            )
            agent_rows = await self.db.execute(agent_stmt)
            for r in agent_rows.all():
                m = self._row_to_metrics(r)
                by_agent.append(
                    AgentSlaAgentRow(
                        agent_id=r.agent_id,
                        agent_name=r.agent_name,
                        **m.model_dump(),
                    )
                )

        day_col = cast(AgentChatCall.created_at, Date)
        day_rows = await self.db.execute(
            select(
                day_col.label("day"),
                func.count(AgentChatCall.id).label("call_count"),
                func.coalesce(func.sum(case((AgentChatCall.status == "success", 1), else_=0)), 0).label("success_count"),
                func.coalesce(func.avg(AgentChatCall.latency_ms), 0).label("latency_avg"),
            )
            .where(*filters)
            .group_by(day_col)
            .order_by(day_col)
        )
        by_day = [
            AgentSlaDailyPoint(
                date=r.day.isoformat() if hasattr(r.day, "isoformat") else str(r.day),
                call_count=int(r.call_count or 0),
                success_rate=success_rate(int(r.success_count or 0), int(r.call_count or 0)),
                latency_avg_ms=round(float(r.latency_avg or 0), 2),
            )
            for r in day_rows.all()
        ]

        return AgentSlaReport(
            days=n,
            agent_id=agent_id,
            overview=overview,
            by_route=by_route,
            by_agent=by_agent,
            by_day=by_day,
        )
