"""RAG 业务门面 — 委托 ai_stack.langchain.rag。"""

from app.ai_stack.langchain.rag import (
    build_rag_user_prompt,
    format_hits_context,
    rag_answer,
    retrieve_hits,
)

__all__ = [
    "build_rag_user_prompt",
    "format_hits_context",
    "rag_answer",
    "retrieve_hits",
]
