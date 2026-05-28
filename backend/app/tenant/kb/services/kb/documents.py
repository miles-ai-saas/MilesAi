"""知识库文档上传、列表与删除。"""

from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, NotFoundError
from app.common.schema import PageParams, PageResult
from app.core.logging import get_logger
from app.core.soft_delete import is_marked_deleted, mark_deleted
from app.core.tenant import TenantContext, assert_tenant_access
from app.deletion.document import clear_document_derived_data_async
from app.infra.storage import build_object_key
from app.infra.storage.resolve import resolve_object_storage_async
from app.models.kb import Document, DocumentChunk, DocumentStatus
from app.rag.parse.upload_policy import is_kb_upload_allowed, kb_upload_allowed_hint
from app.tenant.kb.repositories.kb import DocumentChunkRepository, DocumentRepository
from app.tenant.kb.schemas.kb import DocumentChunkOut, DocumentOut
from app.tenant.kb.services.quota import apply_storage_delta, assert_can_upload_bytes

logger = get_logger(__name__)


class KnowledgeBaseDocumentMixin:
    """文档 CRUD、上传与 Celery ingest 投递。"""

    db: AsyncSession
    ctx: TenantContext
    doc_repo: DocumentRepository
    chunk_repo: DocumentChunkRepository

    async def list_documents(self, kb_id: UUID, params: PageParams) -> PageResult[DocumentOut]:
        """分页列出文档；READY 文档附带分片数量。"""
        await self._get_kb_or_raise(kb_id)
        page = await self.doc_repo.list_page(
            page=params.page,
            size=params.size,
            filters=[Document.kb_id == kb_id],
            order_by=Document.created_at.desc(),
        )
        ready_ids = [d.id for d in page.items if d.status == DocumentStatus.READY]
        chunk_counts = await self.chunk_repo.count_by_document_ids(ready_ids)
        items = []
        for doc in page.items:
            out = DocumentOut.model_validate(doc)
            count = chunk_counts.get(doc.id) if doc.status == DocumentStatus.READY else None
            items.append(out.model_copy(update={"chunk_count": count}))
        return PageResult(
            items=items,
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def list_document_chunks(
        self,
        kb_id: UUID,
        document_id: UUID,
        params: PageParams,
    ) -> PageResult[DocumentChunkOut]:
        """分页列出文档在 PG 中的分片正文（chunk_index 升序）。"""
        await self._get_kb_or_raise(kb_id)
        doc = await self.doc_repo.get_by_id_or_raise(document_id, label="文档不存在")
        if doc.kb_id != kb_id or is_marked_deleted(doc):
            raise NotFoundError("文档不存在")
        assert_tenant_access(self.ctx, doc.tenant_id)
        page = await self.chunk_repo.list_page(
            page=params.page,
            size=params.size,
            filters=[
                DocumentChunk.document_id == document_id,
                DocumentChunk.kb_id == kb_id,
            ],
            order_by=DocumentChunk.chunk_index.asc(),
        )
        return PageResult(
            items=[DocumentChunkOut.model_validate(c) for c in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def upload_document(
        self,
        kb_id: UUID,
        file: UploadFile,
    ) -> DocumentOut:
        """校验类型与配额 → OSS → 建 Document → 投递 Celery ingest。"""
        kb = await self._get_kb_or_raise(kb_id)
        if not file.filename:
            raise BadRequestError("文件名不能为空")
        content = await file.read()
        await assert_can_upload_bytes(self.db, kb.tenant_id, len(content))
        mime = file.content_type or "application/octet-stream"
        if not is_kb_upload_allowed(file.filename, mime):
            raise BadRequestError(f"不支持的文件类型: {mime}。{kb_upload_allowed_hint()}")

        storage = await resolve_object_storage_async(kb.tenant_id, self.db)
        doc = await self.doc_repo.create(
            tenant_id=kb.tenant_id,
            kb_id=kb.id,
            filename=file.filename,
            mime_type=mime,
            file_size=len(content),
            object_bucket=storage.default_bucket,
            object_key="pending",
            status=DocumentStatus.PENDING,
        )
        object_key = build_object_key(str(kb.tenant_id), str(kb.id), str(doc.id), file.filename)
        doc.object_key = object_key
        storage.storage.upload_bytes(content, object_key, mime)
        await self.db.flush()

        from app.workers.tasks.ingest import ingest_document
        from app.tenant.tasks.services.task import TaskService

        task = ingest_document.delay(str(doc.id))
        doc.celery_task_id = task.id
        await TaskService(self.db, self.ctx).create_record(
            celery_task_id=task.id,
            task_name="ingest_document",
            resource_type="document",
            resource_id=doc.id,
        )
        await apply_storage_delta(self.db, kb.tenant_id, len(content))
        await self.db.flush()
        await self.db.refresh(doc)
        return DocumentOut.model_validate(doc)

    async def upload_documents_batch(
        self,
        kb_id: UUID,
        files: list[UploadFile],
    ) -> list[DocumentOut]:
        """批量上传文档（顺序处理，单文件失败不中断）。"""
        if not files:
            raise BadRequestError("请至少选择一个文件")
        if len(files) > 20:
            raise BadRequestError("单次最多上传 20 个文件")
        results: list[DocumentOut] = []
        errors: list[str] = []
        for file in files:
            try:
                results.append(await self.upload_document(kb_id, file))
            except Exception as exc:
                name = file.filename or "未命名"
                errors.append(f"{name}: {exc}")
        if not results and errors:
            raise BadRequestError("；".join(errors[:5]))
        return results

    async def retry_document(self, kb_id: UUID, document_id: UUID) -> DocumentOut:
        """失败或已完成文档重新入库（pipeline 内会先清旧分片/向量）。"""
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
        if not doc.object_key or doc.object_key == "pending":
            raise BadRequestError("文档文件不可用，请重新上传")

        from app.workers.tasks.ingest import ingest_document
        from app.tenant.tasks.services.task import TaskService

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
        """删除衍生数据、OSS 对象并软删文档行。"""
        await self._get_kb_or_raise(kb_id)
        doc = await self.doc_repo.get_by_id_or_raise(document_id, label="文档不存在")
        if doc.kb_id != kb_id or is_marked_deleted(doc):
            raise NotFoundError("文档不存在")
        await clear_document_derived_data_async(self.db, doc.id)
        if doc.object_key and doc.object_key != "pending":
            try:
                storage = await resolve_object_storage_async(doc.tenant_id, self.db)
                storage.storage.delete_object(doc.object_key, doc.object_bucket)
            except Exception:
                logger.warning(
                    "删除文档 OSS 对象失败 document_id=%s object_key=%s",
                    document_id,
                    doc.object_key,
                    exc_info=True,
                )
        size = doc.file_size or 0
        await mark_deleted(self.db, doc)
        if size > 0:
            await apply_storage_delta(self.db, doc.tenant_id, 0)
