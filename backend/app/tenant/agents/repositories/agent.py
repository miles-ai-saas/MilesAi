"""
智能体仓储（L3）。

``load_kbs`` 仅按 id 加载行，**不**校验是否同属当前租户（由 Service 层在绑定前校验）。
``get_detail`` 预加载 knowledge_bases / model_config / published_flow，供 ``AgentService.chat`` 使用。
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.repository import BaseRepository
from app.core.soft_delete import not_deleted
from app.models.agent import Agent, AgentSubAgentBinding
from app.models.kb import KnowledgeBase


class AgentRepository(BaseRepository[Agent]):
    """智能体表仓储（含 KB、子 Agent、模型、流程预加载）。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Agent)

    _eager = [
        selectinload(Agent.knowledge_bases),
        selectinload(Agent.model_config),
        selectinload(Agent.published_flow),
        selectinload(Agent.sub_agent_bindings).selectinload(AgentSubAgentBinding.child_agent),
    ]

    async def get_detail(self, agent_id: UUID) -> Agent | None:
        """加载对话编排所需的关联实体。"""
        stmt = (
            select(Agent)
            .where(Agent.id == agent_id, not_deleted(Agent))
            .options(*self._eager)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def load_kbs(self, kb_ids: list[UUID]) -> list[KnowledgeBase]:
        """创建/更新 Agent 时批量加载知识库行。"""
        if not kb_ids:
            return []
        result = await self.db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id.in_(kb_ids), not_deleted(KnowledgeBase))
        )
        return list(result.scalars().all())
