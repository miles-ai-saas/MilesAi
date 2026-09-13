"""知识库域 ORM（kb_* 表）。"""

from miles_core.models.kb.knowledge_base import (
    Document,
    DocumentChunk,
    DocumentStatus,
    KnowledgeBase,
    VectorRef,
)
from miles_core.models.kb.search_log import KbSearchLog

__all__ = [
    "Document",
    "DocumentChunk",
    "DocumentStatus",
    "KbSearchLog",
    "KnowledgeBase",
    "VectorRef",
]
