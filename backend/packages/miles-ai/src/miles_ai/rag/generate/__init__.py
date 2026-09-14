"""
RAG 生成子包（L2，线性路径）。

导出
----
- ``retrieve_hits``：多 KB 检索（画布、LangGraph retrieve 节点）
- ``build_rag_prompt`` / ``generate_rag_answer``：拼 prompt + 生成（生成阶段无 db）
- ``rag_answer``：检索 + 生成一站式（兼容保留，Task 6 删除）
- ``format_hits_context`` / ``build_rag_user_prompt``：拼 LLM 输入

Agent 默认多轮 RAG 图见 ``integrations.langgraph.graphs.rag_qa``，非本包。
"""

from miles_ai.rag.generate.answer import (
    build_rag_prompt,
    generate_rag_answer,
    rag_answer,
    retrieve_hits,
)
from miles_ai.rag.generate.context import build_rag_user_prompt, format_hits_context

__all__ = [
    "build_rag_prompt",
    "build_rag_user_prompt",
    "format_hits_context",
    "generate_rag_answer",
    "rag_answer",
    "retrieve_hits",
]
