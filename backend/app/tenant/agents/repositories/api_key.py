"""智能体 API Key 仓储。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.models.agent.api_key import AgentApiKey


class AgentApiKeyRepository(BaseRepository[AgentApiKey]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, AgentApiKey)

    async def get_by_hash(self, key_hash: str) -> AgentApiKey | None:
        stmt = select(AgentApiKey).where(AgentApiKey.key_hash == key_hash)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def count_active(self, tenant_id: UUID, agent_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(AgentApiKey)
            .where(
                AgentApiKey.tenant_id == tenant_id,
                AgentApiKey.agent_id == agent_id,
                AgentApiKey.revoked_at.is_(None),
            )
        )
        return int(await self.db.scalar(stmt) or 0)

    async def list_by_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        include_revoked: bool = False,
    ) -> list[AgentApiKey]:
        stmt = select(AgentApiKey).where(
            AgentApiKey.tenant_id == tenant_id,
            AgentApiKey.agent_id == agent_id,
        )
        if not include_revoked:
            stmt = stmt.where(AgentApiKey.revoked_at.is_(None))
        stmt = stmt.order_by(AgentApiKey.created_at.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def touch_last_used(self, key: AgentApiKey) -> None:
        key.last_used_at = datetime.now(timezone.utc)
        await self.db.flush()
