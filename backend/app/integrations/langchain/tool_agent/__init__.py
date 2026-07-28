"""
智能体工具调用循环（无知识库绑定时可选）。

有 KB 时：若 enable_generative_tools 和/或绑定技能包且 enable_tool_calling，
走本包（knowledge_search + 可选 generate_*）；否则走 LangGraph/线性 RAG。
"""

from app.integrations.langchain.tool_agent.artifacts import artifacts_from_tool_output
from app.integrations.langchain.tool_agent.loop import run_tool_calling_chat

__all__ = [
    "artifacts_from_tool_output",
    "run_tool_calling_chat",
]
