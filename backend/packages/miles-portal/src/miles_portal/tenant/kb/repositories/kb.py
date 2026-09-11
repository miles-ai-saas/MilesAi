"""知识库、文档、分片与向量引用表仓储（L3 数据访问）。

被 KnowledgeBaseService 与 ingest 管道间接使用；不承载业务规则。
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.repository import BaseRepository
from miles_core.models.kb import Document, DocumentChunk, KnowledgeBase, VectorRef


class KnowledgeBaseRepository(BaseRepository[KnowledgeBase]):
    """knowledge_bases 表 CRUD。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, KnowledgeBase)


class DocumentRepository(BaseRepository[Document]):
    """kb_documents 表 CRUD。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Document)


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    """kb_document_chunks 表 CRUD。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, DocumentChunk)

    async def count_by_document_ids(self, document_ids: list[UUID]) -> dict[UUID, int]:
        """批量统计各文档分片数（用于列表展示 chunk_count）。"""
        if not document_ids:
            return {}
        stmt = select(DocumentChunk.document_id, func.count()).where(DocumentChunk.document_id.in_(document_ids)).group_by(DocumentChunk.document_id)
        rows = (await self.db.execute(stmt)).all()
        return {doc_id: int(count) for doc_id, count in rows}


class VectorRefRepository(BaseRepository[VectorRef]):
    """kb_vector_refs：分片与向量库 external_id 映射。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, VectorRef)

    async def list_by_document(self, document_id: UUID) -> list[VectorRef]:
        """列出某文档下所有分片的向量引用。"""
        result = await self.db.execute(select(VectorRef).join(DocumentChunk).where(DocumentChunk.document_id == document_id))
        return list(result.scalars().all())
