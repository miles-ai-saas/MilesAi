"""智能体 API Key 仓储。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.repository import BaseRepository
from miles_core.models.agent.api_key import AgentApiKey


class AgentApiKeyRepository(BaseRepository[AgentApiKey]):
    """智能体 API Key 表 ``agt_agent_api_keys`` 的仓储。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, AgentApiKey)

    async def get_by_hash(self, key_hash: str) -> AgentApiKey | None:
        """按密钥哈希查询记录，未命中返回 ``None``。"""
        stmt = select(AgentApiKey).where(AgentApiKey.key_hash == key_hash)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def count_active(self, tenant_id: UUID, agent_id: UUID) -> int:
        """统计该智能体未吊销的密钥数，用于创建时的数量上限校验。"""
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
        """列出智能体密钥，默认排除已吊销；按创建时间倒序。"""
        stmt = select(AgentApiKey).where(
            AgentApiKey.tenant_id == tenant_id,
            AgentApiKey.agent_id == agent_id,
        )
        if not include_revoked:
            stmt = stmt.where(AgentApiKey.revoked_at.is_(None))
        stmt = stmt.order_by(AgentApiKey.created_at.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def touch_last_used(self, key: AgentApiKey) -> None:
        """刷新密钥最后使用时间为当前 UTC（仅 flush，由调用方决定提交）。"""
        key.last_used_at = datetime.now(timezone.utc)
        await self.db.flush()
