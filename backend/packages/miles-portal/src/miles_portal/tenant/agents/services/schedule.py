"""智能体定时任务 CRUD。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.cron import compute_next_run, validate_cron
from miles_common.exceptions import BadRequestError, NotFoundError
from miles_core.service import BaseService
from miles_core.soft_delete import append_not_deleted, is_marked_deleted, mark_deleted
from miles_core.tenant import TenantContext, assert_tenant_access, tenant_filters
from miles_core.models.agent.schedule import AgentSchedule
from miles_core.models.agent.schedule_run import AgentScheduleRun
from miles_common.schema import PageParams, PageResult
from miles_portal.tenant.agents.schemas.schedule import AgentScheduleCreate, AgentScheduleOut, AgentScheduleUpdate
from miles_portal.tenant.agents.schemas.schedule_run import AgentScheduleRunOut
from miles_portal.tenant.agents.services.agent import AgentService


class AgentScheduleService(BaseService):
    """智能体定时任务的 CRUD 与执行历史查询。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self._agents = AgentService(db, ctx)

    async def _get_schedule_or_raise(self, agent_id: UUID, schedule_id: UUID) -> AgentSchedule:
        await self._agents.get_agent_or_raise(agent_id)
        schedule = await self.db.get(AgentSchedule, schedule_id)
        if not schedule or is_marked_deleted(schedule) or schedule.agent_id != agent_id:
            raise NotFoundError("定时任务不存在")
        assert_tenant_access(self.ctx, schedule.tenant_id)
        return schedule

    async def list_schedules(self, agent_id: UUID, params: PageParams) -> PageResult[AgentScheduleOut]:
        """分页列出智能体未删除的定时任务，按创建时间倒序。"""
        await self._agents.get_agent_or_raise(agent_id)
        filters = append_not_deleted(
            tenant_filters(self.ctx, AgentSchedule.tenant_id) + [AgentSchedule.agent_id == agent_id],
            AgentSchedule,
        )
        total = await self.db.scalar(select(func.count()).select_from(AgentSchedule).where(*filters))
        stmt = select(AgentSchedule).where(*filters).order_by(AgentSchedule.created_at.desc()).offset((params.page - 1) * params.size).limit(params.size)
        items = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[AgentScheduleOut.from_model(i) for i in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def create_schedule(self, agent_id: UUID, body: AgentScheduleCreate) -> AgentScheduleOut:
        """创建定时任务；Cron 非法抛 ``BadRequestError``，启用时计算下次执行时间。"""
        agent = await self._agents.get_agent_or_raise(agent_id)
        try:
            cron = validate_cron(body.cron)
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc

        schedule = AgentSchedule(
            tenant_id=agent.tenant_id,
            agent_id=agent_id,
            content=body.content.strip(),
            cron=cron,
            enabled=body.enabled,
            created_by=self.ctx.user_id,
            next_run_at=compute_next_run(cron) if body.enabled else None,
        )
        self.db.add(schedule)
        await self.db.flush()
        await self.db.refresh(schedule)
        return AgentScheduleOut.from_model(schedule)

    async def update_schedule(self, agent_id: UUID, schedule_id: UUID, body: AgentScheduleUpdate) -> AgentScheduleOut:
        """更新定时任务；按启用状态与 Cron 重算下次执行时间。"""
        schedule = await self._get_schedule_or_raise(agent_id, schedule_id)

        if body.content is not None:
            schedule.content = body.content.strip()
        if body.cron is not None:
            try:
                schedule.cron = validate_cron(body.cron)
            except ValueError as exc:
                raise BadRequestError(str(exc)) from exc
        if body.enabled is not None:
            schedule.enabled = body.enabled

        if schedule.enabled:
            schedule.next_run_at = compute_next_run(schedule.cron)
        else:
            schedule.next_run_at = None

        await self.db.flush()
        await self.db.refresh(schedule)
        return AgentScheduleOut.from_model(schedule)

    async def delete_schedule(self, agent_id: UUID, schedule_id: UUID) -> None:
        """软删除定时任务。"""
        schedule = await self._get_schedule_or_raise(agent_id, schedule_id)
        mark_deleted(schedule)
        await self.db.flush()

    async def list_runs(self, agent_id: UUID, schedule_id: UUID, params: PageParams) -> PageResult[AgentScheduleRunOut]:
        """分页查询定时任务执行历史，按开始时间倒序。"""
        await self._get_schedule_or_raise(agent_id, schedule_id)
        filters = tenant_filters(self.ctx, AgentScheduleRun.tenant_id) + [
            AgentScheduleRun.schedule_id == schedule_id,
            AgentScheduleRun.agent_id == agent_id,
        ]
        total = await self.db.scalar(select(func.count()).select_from(AgentScheduleRun).where(*filters))
        stmt = select(AgentScheduleRun).where(*filters).order_by(AgentScheduleRun.started_at.desc()).offset((params.page - 1) * params.size).limit(params.size)
        items = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[AgentScheduleRunOut.from_model(i) for i in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )
