"""兼容转发 → app.rag.generate。"""

from app.rag.generate import (
    build_rag_user_prompt,
    format_hits_context,
    rag_answer,
    retrieve_hits,
    retrieve_hits_with_ctx,
)

__all__ = [
    "build_rag_user_prompt",
    "format_hits_context",
    "rag_answer",
    "retrieve_hits",
    "retrieve_hits_with_ctx",
]
