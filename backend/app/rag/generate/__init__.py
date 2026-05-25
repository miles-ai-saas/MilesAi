"""RAG 生成：检索命中 + 拼装 prompt + LLM 回答。"""

from app.rag.generate.answer import rag_answer, retrieve_hits, retrieve_hits_with_ctx
from app.rag.generate.context import build_rag_user_prompt, format_hits_context

__all__ = [
    "build_rag_user_prompt",
    "format_hits_context",
    "rag_answer",
    "retrieve_hits",
    "retrieve_hits_with_ctx",
]
