"""Views 层 Service 工厂（共享给各子路由模块）。"""

from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.tenant import TenantContext
from miles_portal.tenant.agents.services.agent import AgentService
from miles_portal.tenant.agents.services.api_access import AgentApiAccessService
from miles_portal.tenant.agents.services.architecture import AgentArchitectureService
from miles_portal.tenant.agents.services.call_records import AgentCallRecordService
from miles_portal.tenant.agents.services.chat_sessions import AgentChatSessionService
from miles_portal.tenant.agents.services.schedule import AgentScheduleService
from miles_portal.tenant.agents.services.stats import AgentStatsService
from miles_portal.tenant.agents.services.user_memory import UserMemoryService


def agent_svc(db: AsyncSession, ctx: TenantContext) -> AgentService:
    return AgentService(db, ctx)


def user_memory_svc(db: AsyncSession, ctx: TenantContext) -> UserMemoryService:
    return UserMemoryService(db, ctx)


def api_access_svc(db: AsyncSession, ctx: TenantContext) -> AgentApiAccessService:
    return AgentApiAccessService(db, ctx)


def stats_svc(db: AsyncSession, ctx: TenantContext) -> AgentStatsService:
    return AgentStatsService(db, ctx)


def arch_svc(db: AsyncSession, ctx: TenantContext) -> AgentArchitectureService:
    return AgentArchitectureService(db, ctx)


def schedule_svc(db: AsyncSession, ctx: TenantContext) -> AgentScheduleService:
    return AgentScheduleService(db, ctx)


def call_record_svc(db: AsyncSession, ctx: TenantContext) -> AgentCallRecordService:
    return AgentCallRecordService(db, ctx)


def chat_session_svc(db: AsyncSession, ctx: TenantContext) -> AgentChatSessionService:
    return AgentChatSessionService(db, ctx)
