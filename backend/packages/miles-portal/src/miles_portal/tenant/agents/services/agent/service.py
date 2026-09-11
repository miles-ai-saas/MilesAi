"""
智能体 CRUD 与对话编排（L2）。

``chat`` 决策顺序（自上而下命中即返回）
-------------------------------------
1. A2A Host 模式（``agent_type=a2a`` 等）
2. 子智能体绑定 → DeepAgents 规划
3. A2A Peer 增强（有 peer 且无子 Agent 时）
4. ``published_flow_id`` → 流程画布运行时
5. 默认 **RAG**：``rag_chat`` → LangGraph 或线性 ``rag_answer``

子模块见同目录 ``crud`` / ``chat`` / ``serialization``；包说明见 ``agent.__init__``。
对外仅从此包导入 ``AgentService``（``from miles_portal.tenant.agents.services.agent import …``）。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.tenant import TenantContext
from miles_portal.tenant.agents.services.agent.chat import AgentChatMixin
from miles_portal.tenant.agents.services.agent.crud import AgentCrudMixin
from miles_portal.tenant.agents.services.agent.serialization import agent_out
from miles_portal.tenant.flows.repositories.flow import FlowRepository


class AgentService(AgentChatMixin, AgentCrudMixin):
    """智能体 CRUD；chat 按类型路由 A2A/子 Agent/流程/RAG。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        """组合 CRUD/对话 Mixin，并注入流程版本仓库。"""
        AgentCrudMixin.__init__(self, db, ctx)
        self.flow_repo = FlowRepository(db)


_agent_out = agent_out
