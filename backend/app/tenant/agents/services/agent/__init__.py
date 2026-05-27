"""
Agent 聚合：CRUD + 对话编排。

目录职责
--------
- ``service.py``：``AgentService`` 门面（组合 CRUD / 对话 Mixin）。
- ``crud.py``：元数据、列表/创建/更新/删除、``resolve_system_prompt``。
- ``chat.py``：``chat`` / ``chat_as_child`` / ``rag_chat`` / 流程与 A2A 路由。
- ``serialization.py``：``agent_out``、``should_use_skill_tools_with_kb``。

不在此包内（位于 ``services/`` 根目录）
--------------------------------------
``architecture``、``schedule``、``stats``、``context``、``sub_agents``。

对外请使用::

    from app.tenant.agents.services.agent import AgentService, should_use_skill_tools_with_kb
"""

from app.tenant.agents.services.agent.serialization import (
    agent_out,
    should_use_skill_tools_with_kb,
)
from app.tenant.agents.services.agent.service import AgentService, _agent_out

__all__ = [
    "AgentService",
    "agent_out",
    "should_use_skill_tools_with_kb",
    "_agent_out",
]
