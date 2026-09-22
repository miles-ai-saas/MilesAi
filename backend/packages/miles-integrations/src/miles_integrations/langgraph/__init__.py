"""
LangGraph 集成包（L3）：仅保留 checkpointer 生命周期。

RAG 图引擎已归位 ``miles_ai.rag.graph``，画布流程引擎已归位 ``miles_ai.flow_runtime``；
本包不再 re-export 上层编排，避免 L3 反向依赖 L2。

应用启动时经 ``init_langgraph_checkpointer`` 绑定 Redis/Memory，关闭时 ``shutdown_langgraph_checkpointer``。
"""

from miles_integrations.langgraph.checkpointer import (
    checkpoint_backend,
    get_checkpointer,
    init_langgraph_checkpointer,
    shutdown_langgraph_checkpointer,
)

__all__ = [
    "checkpoint_backend",
    "get_checkpointer",
    "init_langgraph_checkpointer",
    "shutdown_langgraph_checkpointer",
]
