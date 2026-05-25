"""
RAG 生成子包（L2，线性路径）。

导出
----
- ``retrieve_hits`` / ``retrieve_hits_with_ctx``：多 KB 检索（画布、LangGraph retrieve 节点）
- ``rag_answer``：检索 + ``ainvoke_chat`` 一站式
- ``format_hits_context`` / ``build_rag_user_prompt``：拼 LLM 输入

Agent 默认多轮 RAG 图见 ``integrations.langgraph.graphs.rag_qa``，非本包。
"""

from app.rag.generate.answer import rag_answer, retrieve_hits, retrieve_hits_with_ctx
from app.rag.generate.context import build_rag_user_prompt, format_hits_context

__all__ = [
    "build_rag_user_prompt",
    "format_hits_context",
    "rag_answer",
    "retrieve_hits",
    "retrieve_hits_with_ctx",
]
