"""兼容转发 → app.rag.retrieve.keyword。"""

from app.rag.retrieve.keyword import (
    search_chunks_by_keyword,
    search_chunks_by_keyword_sync,
)

__all__ = ["search_chunks_by_keyword", "search_chunks_by_keyword_sync"]
