"""智能体 API 对接调试：签发短期 access JWT。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundError
from app.core.config import get_settings
from app.core.security import create_access_token
from app.core.service import BaseService
from app.core.tenant import TenantContext, assert_tenant_access
from app.tenant.agents.repositories.agent import AgentRepository
from app.tenant.agents.schemas.api_access import DEBUG_TOKEN_WARNING, AgentDebugTokenOut
from app.tenant.auth.services import session_store


class AgentApiAccessService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = AgentRepository(db)

    async def create_debug_token(
        self,
        agent_id: UUID,
        *,
        user_agent: str | None = None,
        ip: str | None = None,
    ) -> AgentDebugTokenOut:
        assert self.ctx is not None
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundError("智能体不存在")
        assert_tenant_access(self.ctx, agent.tenant_id)

        settings = get_settings()
        ttl_hours = max(1, int(settings.agent_api_debug_token_ttl_hours))
        expires_delta = timedelta(hours=ttl_hours)
        expires_at = datetime.now(timezone.utc) + expires_delta
        token = create_access_token(
            str(self.ctx.user_id),
            {
                "tenant_id": str(self.ctx.tenant_id),
                "is_superuser": self.ctx.is_superuser,
                "purpose": "agent_api_debug",
                "agent_id": str(agent_id),
            },
            expires_delta=expires_delta,
        )
        await session_store.register_session(
            self.ctx.user_id,
            token,
            user_agent=user_agent or "agent-api-debug",
            ip=ip,
        )
        return AgentDebugTokenOut(
            access_token=token,
            token_type="bearer",
            expires_in=int(expires_delta.total_seconds()),
            expires_at=expires_at,
            agent_id=agent_id,
            purpose="agent_api_debug",
            warning=DEBUG_TOKEN_WARNING,
        )
