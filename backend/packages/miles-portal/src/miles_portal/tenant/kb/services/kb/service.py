"""
KnowledgeBaseService 门面。

通过 Mixin 组合 core / documents / search 子模块；``__init__`` 注入 KB 相关仓库。
对外仅从此包 ``__init__.py`` 导入 ``KnowledgeBaseService``。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.service import BaseService
from miles_core.tenant import TenantContext
from miles_portal.tenant.kb.repositories.kb import (
    DocumentChunkRepository,
    DocumentRepository,
    KnowledgeBaseRepository,
    VectorRefRepository,
)
from miles_portal.tenant.kb.services.kb.core import KnowledgeBaseCoreMixin
from miles_portal.tenant.kb.services.kb.documents import KnowledgeBaseDocumentMixin
from miles_portal.tenant.kb.services.kb.search import KnowledgeBaseSearchMixin


class KnowledgeBaseService(
    KnowledgeBaseSearchMixin,
    KnowledgeBaseDocumentMixin,
    KnowledgeBaseCoreMixin,
    BaseService,
):
    """上传后仅落 OSS + 建 Document 行并投递 Celery；解析索引见 rag.pipeline。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        """注入异步 DB 会话与租户上下文。"""
        super().__init__(db, ctx)
        self.kb_repo = KnowledgeBaseRepository(db)
        self.doc_repo = DocumentRepository(db)
        self.chunk_repo = DocumentChunkRepository(db)
        self.vector_repo = VectorRefRepository(db)
