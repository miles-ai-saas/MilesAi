"""
智能体 HTTP API。

``POST /{id}/chat`` 委托 ``AgentService.chat``，内部按 A2A/子 Agent/流程/RAG 优先级编排；
知识库检索细节见 ``tenant.agents.services.agent`` 子包 ``rag_chat`` 与 ``integrations.langgraph``。

子模块按资源拆分：``crud`` / ``chat`` / ``sessions`` / ``memories`` / ``schedules`` /
``call_records`` / ``api_access``；对外仍 ``from …views import agents`` → ``agents.router``。
"""

# 导入子模块：将 path 挂到共享 ``router``（副作用注册）
from miles_portal.tenant.agents.views.agents import (  # noqa: E402, F401
    api_access,
    call_records,
    chat,
    crud,
    memories,
    schedules,
    sessions,
)
from miles_portal.tenant.agents.views.agents.router import router

__all__ = ["router"]
