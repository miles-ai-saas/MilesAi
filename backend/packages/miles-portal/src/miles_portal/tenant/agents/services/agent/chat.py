"""智能体对话编排：组合 Turn / Entry / Rag Mixin。

路由优先级与 ``AgentService`` / ``architecture`` 一致：
A2A Host → 子 Agent 规划 → A2A Peer → published_flow 画布 → ``rag_chat``。
每条路径均经合规 scan + Hook 包裹，出站再 ``check_output``。
"""

from __future__ import annotations

from miles_portal.tenant.agents.services.agent.chat_entry import AgentChatEntryMixin
from miles_portal.tenant.agents.services.agent.chat_rag import AgentChatRagMixin
from miles_portal.tenant.agents.services.agent.chat_turn import AgentChatTurnMixin


class AgentChatMixin(AgentChatEntryMixin, AgentChatRagMixin, AgentChatTurnMixin):
    """对话路由与 RAG；依赖 AgentCrudMixin 的加载与 prompt 解析。"""

    pass
