"""
RAG 生成子包（L2，线性路径）。

导出
----
- ``retrieve_hits``：多 KB 检索（画布、LangGraph retrieve 节点）
- ``build_rag_prompt`` / ``generate_rag_answer``：拼 prompt + 生成（生成阶段无 db）
- ``format_hits_context`` / ``build_rag_user_prompt``：拼 LLM 输入

Agent 默认多轮 RAG 图见 ``rag.graph.rag_qa``，非本包。
"""

from miles_ai.rag.generate.answer import (
    build_rag_prompt,
    generate_rag_answer,
    retrieve_hits,
)
from miles_ai.rag.generate.context import build_rag_user_prompt, format_hits_context

__all__ = [
    "build_rag_prompt",
    "build_rag_user_prompt",
    "format_hits_context",
    "generate_rag_answer",
    "retrieve_hits",
]
