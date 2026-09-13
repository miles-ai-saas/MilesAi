"""知识库仓储包导出。"""

from miles_portal.tenant.kb.repositories.kb import (
    DocumentChunkRepository,
    DocumentRepository,
    KnowledgeBaseRepository,
    VectorRefRepository,
)

__all__ = [
    "DocumentChunkRepository",
    "DocumentRepository",
    "KnowledgeBaseRepository",
    "VectorRefRepository",
]
