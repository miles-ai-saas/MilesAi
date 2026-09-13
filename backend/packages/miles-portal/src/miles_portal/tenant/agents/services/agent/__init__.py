"""
Agent 聚合：CRUD + 对话编排。

目录职责
--------
- ``service.py``：``AgentService`` 门面（组合 CRUD / 对话 Mixin）。
- ``crud.py``：元数据、列表/创建/更新/删除、``resolve_system_prompt``。
- ``chat.py``：``AgentChatMixin`` 组合门面。
- ``chat_entry.py``：``chat`` / ``chat_as_child`` 入口。
- ``chat_rag.py``：``rag_chat`` / ``direct_chat`` / 流程 RunContext / A2A 增强。
- ``chat_turn.py``：单轮收尾、RAG 路由解析、调用记录。
- ``serialization.py``：``agent_out``、``should_use_tools_with_kb``。

不在此包内（位于 ``services/`` 根目录）
--------------------------------------
``architecture``、``schedule``、``stats``、``context``、``sub_agents``。

对外请使用::

    from miles_portal.tenant.agents.services.agent import AgentService, should_use_tools_with_kb
"""

from miles_portal.tenant.agents.services.agent.serialization import (
    agent_out,
    should_use_tools_with_kb,
)
from miles_portal.tenant.agents.services.agent.service import AgentService, _agent_out

__all__ = [
    "AgentService",
    "_agent_out",
    "agent_out",
    "should_use_tools_with_kb",
]
