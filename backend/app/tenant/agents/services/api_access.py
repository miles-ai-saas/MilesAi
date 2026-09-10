"""智能体 API 对接：调试 Token + 正式 API Key CRUD。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, NotFoundError
from app.core.config import get_settings
from app.core.security import create_access_token
from app.core.service import BaseService
from app.core.tenant import TenantContext, assert_tenant_access
from app.models.agent.api_key import AgentApiKey
from app.tenant.agents.repositories.agent import AgentRepository
from app.tenant.agents.repositories.api_key import AgentApiKeyRepository
from app.tenant.agents.schemas.api_access import (
    API_KEY_CREATED_WARNING,
    DEBUG_TOKEN_WARNING,
    MAX_ACTIVE_AGENT_API_KEYS,
    AgentApiKeyCreate,
    AgentApiKeyCreatedOut,
    AgentApiKeyOut,
    AgentDebugTokenOut,
)
from app.tenant.agents.services.api_key_crypto import generate_agent_api_key_secret
from app.tenant.auth.services import session_store


def _key_out(row: AgentApiKey) -> AgentApiKeyOut:
    return AgentApiKeyOut(
        id=row.id,
        name=row.name,
        key_prefix=row.key_prefix,
        status="revoked" if row.revoked_at else "active",
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        revoked_at=row.revoked_at,
    )


class AgentApiAccessService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = AgentRepository(db)
        self.keys = AgentApiKeyRepository(db)

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

    async def _require_agent(self, agent_id: UUID):
        assert self.ctx is not None
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundError("智能体不存在")
        assert_tenant_access(self.ctx, agent.tenant_id)
        return agent

    async def create_api_key(self, agent_id: UUID, body: AgentApiKeyCreate) -> AgentApiKeyCreatedOut:
        assert self.ctx is not None
        agent = await self._require_agent(agent_id)
        active = await self.keys.count_active(agent.tenant_id, agent_id)
        if active >= MAX_ACTIVE_AGENT_API_KEYS:
            raise BadRequestError(f"每个智能体最多 {MAX_ACTIVE_AGENT_API_KEYS} 个有效密钥，请先吊销后再创建")
        plain, prefix, digest = generate_agent_api_key_secret()
        row = await self.keys.create(
            tenant_id=agent.tenant_id,
            agent_id=agent_id,
            name=body.name.strip(),
            key_prefix=prefix,
            key_hash=digest,
            created_by=self.ctx.user_id,
        )
        base = _key_out(row)
        return AgentApiKeyCreatedOut(
            **base.model_dump(),
            secret=plain,
            warning=API_KEY_CREATED_WARNING,
        )

    async def list_api_keys(
        self,
        agent_id: UUID,
        *,
        include_revoked: bool = False,
    ) -> list[AgentApiKeyOut]:
        agent = await self._require_agent(agent_id)
        rows = await self.keys.list_by_agent(agent.tenant_id, agent_id, include_revoked=include_revoked)
        return [_key_out(r) for r in rows]

    async def revoke_api_key(self, agent_id: UUID, key_id: UUID) -> AgentApiKeyOut:
        assert self.ctx is not None
        await self._require_agent(agent_id)
        row = await self.keys.get_by_id(key_id)
        if not row or row.agent_id != agent_id:
            raise NotFoundError("密钥不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        if row.revoked_at is None:
            row.revoked_at = datetime.now(timezone.utc)
            await self.db.flush()
        return _key_out(row)
