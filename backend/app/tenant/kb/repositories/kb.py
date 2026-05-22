"""知识库、文档、分片与向量引用表仓储。"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.models.kb import Document, DocumentChunk, KnowledgeBase, VectorRef


class KnowledgeBaseRepository(BaseRepository[KnowledgeBase]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, KnowledgeBase)


class DocumentRepository(BaseRepository[Document]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Document)


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, DocumentChunk)


class VectorRefRepository(BaseRepository[VectorRef]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, VectorRef)

    async def list_by_document(self, document_id: UUID) -> list[VectorRef]:
        result = await self.db.execute(
            select(VectorRef).join(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        return list(result.scalars().all())
