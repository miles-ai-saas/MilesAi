from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.repository import BaseRepository
from app.models.agent import Agent
from app.models.kb import KnowledgeBase


class AgentRepository(BaseRepository[Agent]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Agent)

    _eager = [
        selectinload(Agent.knowledge_bases),
        selectinload(Agent.model_config),
        selectinload(Agent.published_flow),
    ]

    async def get_detail(self, agent_id: UUID) -> Agent | None:
        stmt = select(Agent).where(Agent.id == agent_id).options(*self._eager)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def load_kbs(self, kb_ids: list[UUID]) -> list[KnowledgeBase]:
        if not kb_ids:
            return []
        result = await self.db.execute(select(KnowledgeBase).where(KnowledgeBase.id.in_(kb_ids)))
        return list(result.scalars().all())
