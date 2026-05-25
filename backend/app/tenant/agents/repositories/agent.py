"""
智能体仓储（L3）。

``load_kbs`` 仅按 id 加载行，**不**校验是否同属当前租户（由 Service 层在绑定前校验）。
``get_detail`` 预加载 knowledge_bases / model_config / published_flow，供 ``AgentService.chat`` 使用。
"""

from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.exceptions import NotFoundError
from app.core.repository import BaseRepository
from app.core.soft_delete import not_deleted
from app.deletion.cascade import unlink_agent_kb_bindings
from app.models.agent import Agent, AgentSubAgentBinding, agent_kb_bindings
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

    async def replace_kb_bindings(
        self,
        agent_id: UUID,
        kb_ids: list[UUID],
        *,
        tenant_id: UUID,
    ) -> None:
        """全量替换 Agent↔KB 关联（直接写关联表，避免 async 下 ORM 懒加载）。"""
        await unlink_agent_kb_bindings(self.db, agent_id=agent_id)
        if not kb_ids:
            return
        rows = (
            await self.db.execute(
                select(KnowledgeBase.id).where(
                    KnowledgeBase.id.in_(kb_ids),
                    KnowledgeBase.tenant_id == tenant_id,
                    not_deleted(KnowledgeBase),
                )
            )
        ).scalars().all()
        found = set(rows)
        if len(found) != len(set(kb_ids)):
            raise NotFoundError("知识库不存在或无权访问")
        await self.db.execute(
            insert(agent_kb_bindings),
            [{"agent_id": agent_id, "kb_id": kb_id} for kb_id in kb_ids],
        )
