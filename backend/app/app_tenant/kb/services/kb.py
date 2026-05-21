from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embedding import embed_query
from app.core.config import get_settings
from app.common.exceptions import BadRequestError, NotFoundError
from app.core.minio_client import build_object_key, delete_object, upload_bytes
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.deletion.cascade import before_delete_kb
from app.deletion.document import clear_document_derived_data_async
from app.core.weaviate_store import search_vectors
from app.models.kb import Document, DocumentChunk, DocumentStatus, KnowledgeBase
from app.app_tenant.kb.repositories.kb import (
    DocumentChunkRepository,
    DocumentRepository,
    KnowledgeBaseRepository,
    VectorRefRepository,
)
from app.common.schema import PageParams, PageResult
from app.app_tenant.kb.schemas.kb import (
    DocumentOut,
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from app.ai.media import file_extension, is_audio_file, is_image_file
from app.core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from app.core.service import BaseService

settings = get_settings()
ALLOWED_MIMES = {
    "text/plain",
    "text/markdown",
    "application/pdf",
    "application/octet-stream",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/ogg",
}

_ALLOWED_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".mp3",
    ".wav",
    ".m4a",
    ".ogg",
    ".webm",
}


def _is_allowed_upload(filename: str, mime: str) -> bool:
    ext = file_extension(filename)
    if mime in ALLOWED_MIMES or ext in _ALLOWED_EXTENSIONS:
        return True
    return is_image_file(filename, mime) or is_audio_file(filename, mime)


class KnowledgeBaseService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.kb_repo = KnowledgeBaseRepository(db)
        self.doc_repo = DocumentRepository(db)
        self.chunk_repo = DocumentChunkRepository(db)
        self.vector_repo = VectorRefRepository(db)

    async def _get_kb_or_raise(self, kb_id: UUID) -> KnowledgeBase:
        kb = await self.kb_repo.get_by_id(kb_id)
        if not kb or is_marked_deleted(kb):
            raise NotFoundError("知识库不存在")
        assert_tenant_access(self.ctx, kb.tenant_id)
        return kb

    async def list_kbs(self, params: PageParams) -> PageResult[KnowledgeBaseOut]:
        filters = tenant_filters(self.ctx, KnowledgeBase.tenant_id)
        page = await self.kb_repo.list_page(
            page=params.page,
            size=params.size,
            filters=filters,
            order_by=KnowledgeBase.created_at.desc(),
        )
        return PageResult(
            items=[KnowledgeBaseOut.model_validate(k) for k in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def create_kb(self, body: KnowledgeBaseCreate) -> KnowledgeBaseOut:
        kb = await self.kb_repo.create(
            tenant_id=self.ctx.tenant_id,
            name=body.name,
            description=body.description,
            is_public=body.is_public,
            chunk_size=body.chunk_size,
            chunk_overlap=body.chunk_overlap,
            embedding_dimension=384,
        )
        await self.db.refresh(kb)
        return KnowledgeBaseOut.model_validate(kb)

    async def get_kb(self, kb_id: UUID) -> KnowledgeBaseOut:
        kb = await self._get_kb_or_raise(kb_id)
        return KnowledgeBaseOut.model_validate(kb)

    async def update_kb(self, kb_id: UUID, body: KnowledgeBaseUpdate) -> KnowledgeBaseOut:
        kb = await self._get_kb_or_raise(kb_id)
        await self.kb_repo.update_fields(kb, body.model_dump(exclude_unset=True))
        await self.db.refresh(kb)
        return KnowledgeBaseOut.model_validate(kb)

    async def delete_kb(self, kb_id: UUID) -> None:
        kb = await self._get_kb_or_raise(kb_id)
        docs = (
            await self.db.execute(
                select(Document).where(Document.kb_id == kb.id, not_deleted(Document))
            )
        ).scalars().all()
        for doc in docs:
            await self.delete_document(kb_id, doc.id)
        await before_delete_kb(self.db, kb.id)
        await mark_deleted(self.db, kb)

    async def list_documents(self, kb_id: UUID, params: PageParams) -> PageResult[DocumentOut]:
        await self._get_kb_or_raise(kb_id)
        page = await self.doc_repo.list_page(
            page=params.page,
            size=params.size,
            filters=[Document.kb_id == kb_id],
            order_by=Document.created_at.desc(),
        )
        return PageResult(
            items=[DocumentOut.model_validate(d) for d in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def upload_document(
        self,
        kb_id: UUID,
        file: UploadFile,
    ) -> DocumentOut:
        kb = await self._get_kb_or_raise(kb_id)
        if not file.filename:
            raise BadRequestError("文件名不能为空")
        content = await file.read()
        if not content:
            raise BadRequestError("文件内容为空")
        mime = file.content_type or "application/octet-stream"
        if not _is_allowed_upload(file.filename, mime):
            raise BadRequestError(
                f"不支持的文件类型: {mime}。"
                "支持 TXT/MD/PDF、图片（JPG/PNG/WebP）、音频（MP3/WAV）"
            )

        doc = await self.doc_repo.create(
            tenant_id=kb.tenant_id,
            kb_id=kb.id,
            filename=file.filename,
            mime_type=mime,
            file_size=len(content),
            minio_bucket=settings.minio_bucket,
            minio_key="pending",
            status=DocumentStatus.PENDING,
        )
        object_key = build_object_key(
            str(kb.tenant_id), str(kb.id), str(doc.id), file.filename
        )
        doc.minio_key = object_key
        upload_bytes(content, object_key, mime)
        await self.db.flush()

        from app.workers.tasks.ingest import ingest_document
        from app.app_tenant.tasks.services.task import TaskService

        task = ingest_document.delay(str(doc.id))
        doc.celery_task_id = task.id
        await TaskService(self.db, self.ctx).create_record(
            celery_task_id=task.id,
            task_name="ingest_document",
            resource_type="document",
            resource_id=doc.id,
        )
        await self.db.flush()
        await self.db.refresh(doc)
        return DocumentOut.model_validate(doc)

    async def retry_document(self, kb_id: UUID, document_id: UUID) -> DocumentOut:
        await self._get_kb_or_raise(kb_id)
        doc = await self.doc_repo.get_by_id_or_raise(document_id, label="文档不存在")
        if doc.kb_id != kb_id or is_marked_deleted(doc):
            raise NotFoundError("文档不存在")
        if doc.status not in (
            DocumentStatus.PARSE_FAILED,
            DocumentStatus.EMBED_FAILED,
            DocumentStatus.READY,
        ):
            raise BadRequestError("仅失败或已完成的文档可重新入库")
        if not doc.minio_key or doc.minio_key == "pending":
            raise BadRequestError("文档文件不可用，请重新上传")

        from app.workers.tasks.ingest import ingest_document
        from app.app_tenant.tasks.services.task import TaskService

        doc.status = DocumentStatus.PENDING
        doc.fail_reason = None
        task = ingest_document.delay(str(doc.id))
        doc.celery_task_id = task.id
        await TaskService(self.db, self.ctx).create_record(
            celery_task_id=task.id,
            task_name="ingest_document",
            resource_type="document",
            resource_id=doc.id,
        )
        await self.db.flush()
        await self.db.refresh(doc)
        return DocumentOut.model_validate(doc)

    async def delete_document(self, kb_id: UUID, document_id: UUID) -> None:
        await self._get_kb_or_raise(kb_id)
        doc = await self.doc_repo.get_by_id_or_raise(document_id, label="文档不存在")
        if doc.kb_id != kb_id or is_marked_deleted(doc):
            raise NotFoundError("文档不存在")
        await mark_deleted(self.db, doc)

    async def search(self, kb_id: UUID, body: SearchRequest) -> SearchResponse:
        await self._get_kb_or_raise(kb_id)
        query_vector = embed_query(body.query)
        raw_hits = search_vectors(
            query_vector,
            tenant_id=self.ctx.tenant_id,
            kb_id=kb_id,
            limit=body.top_k,
        )
        hits: list[SearchHit] = []
        for h in raw_hits:
            chunk_id = h.get("chunk_id")
            if not chunk_id:
                continue
            chunk = await self.chunk_repo.get_by_id(UUID(chunk_id))
            if not chunk:
                continue
            doc = await self.doc_repo.get_by_id(UUID(h["document_id"]))
            if not doc or is_marked_deleted(doc):
                continue
            hits.append(
                SearchHit(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    score=float(h.get("score", 0)),
                    filename=doc.filename if doc else None,
                )
            )
        return SearchResponse(query=body.query, hits=hits)
