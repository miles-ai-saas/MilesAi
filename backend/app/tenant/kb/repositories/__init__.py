"""知识库仓储包导出。"""

from app.tenant.kb.repositories.kb import (
    DocumentChunkRepository,
    DocumentRepository,
    KnowledgeBaseRepository,
    VectorRefRepository,
)

__all__ = [
    "KnowledgeBaseRepository",
    "DocumentRepository",
    "DocumentChunkRepository",
    "VectorRefRepository",
]
