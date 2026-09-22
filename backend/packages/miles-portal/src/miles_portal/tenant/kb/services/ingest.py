"""
文档入库编排（Celery Worker 同步执行）。

分层
----
- **L1 本模块**：文档状态机（PENDING → PARSING → EMBEDDING → READY/失败）、
  会话外 S3/parse、注入 embedding 回调、调用 ``rag.pipeline.run_ingest_pipeline``。
- **L2 pipeline**：Parse → Chunk → Embed → ``gateway.upsert_chunk_vector``（见 rag 注释）。

调用链
------
``KnowledgeBaseService.upload_document`` → ``ingest_document.delay``
  → ``run_ingest``（本模块）→ ``run_ingest_pipeline``

状态说明
--------
PARSING commit → 短会话 resolve storage → 会话外 download/parse/chunk →
EMBEDDING commit → pipeline（清旧后 commit 再 embed）+ READY。
失败相位：S3/parse 空文本为 PARSING；进 pipeline 后为 EMBEDDING。

失败处理
----------
异常时在**新** ``get_sync_db`` 会话上 ``persist_document_ingest_failure``（内部已 commit），
避免在可能已脏的 index 会话上写失败态。
"""

from uuid import UUID

from miles_ai.rag.chunk import chunk_documents
from miles_ai.rag.parse.loaders import load_documents_from_bytes
from miles_ai.rag.pipeline import IngestInput, run_ingest_pipeline
from miles_core.infra.db import get_sync_db
from miles_core.infra.storage import resolve_object_storage_sync
from miles_core.models.kb import Document, DocumentStatus, KnowledgeBase
from miles_portal.deletion.document import clear_document_derived_data_sync
from miles_portal.tenant.kb.services.embeddings import (
    embed_image_chunks_vectors_sync,
    embed_texts_for_kb_sync,
)
from miles_portal.tenant.kb.services.ingest_failure import persist_document_ingest_failure


def run_ingest(document_id: str) -> None:
    """
    同步执行单文档入库（仅由 Celery Worker 调用，HTTP 不直连）。

    分阶段：PARSING → 会话外 S3/parse → EMBEDDING → pipeline + READY。
    ``on_before_index=clear_document_derived_data_sync``：覆盖/重试入库前删除旧分片与向量。
    """
    phase = DocumentStatus.PARSING
    doc_uuid = UUID(document_id)
    try:
        with get_sync_db() as db:
            doc = db.get(Document, doc_uuid)
            if not doc or doc.deleted_at is not None:
                return
            kb = db.get(KnowledgeBase, doc.kb_id)
            if not kb or kb.deleted_at is not None:
                return
            doc.status = DocumentStatus.PARSING
            doc.fail_reason = None
            tenant_id = doc.tenant_id
            object_key = doc.object_key
            object_bucket = doc.object_bucket
            filename = doc.filename
            mime_type = doc.mime_type
            chunk_size = kb.chunk_size
            chunk_overlap = kb.chunk_overlap

        with get_sync_db() as db:
            resolved = resolve_object_storage_sync(tenant_id, db)

        # S3 与 parse/chunk 在会话外执行，避免长事务占连接
        raw = resolved.storage.download_bytes(object_key, bucket=object_bucket)
        docs = load_documents_from_bytes(raw, filename, mime_type)
        chunks = chunk_documents(docs, chunk_size, chunk_overlap)
        if not chunks:
            raise ValueError("未能提取有效文本")

        with get_sync_db() as db:
            doc = db.get(Document, doc_uuid)
            if not doc or doc.deleted_at is not None:
                return
            kb = db.get(KnowledgeBase, doc.kb_id)
            if not kb or kb.deleted_at is not None:
                # PARSING 已提交：KB 消失须写失败态，避免文档永久卡在 PARSING
                raise ValueError("知识库不存在或已删除")
            doc.status = DocumentStatus.EMBEDDING
            phase = DocumentStatus.EMBEDDING

        with get_sync_db() as db:
            doc = db.get(Document, doc_uuid)
            if not doc or doc.deleted_at is not None:
                return
            kb = db.get(KnowledgeBase, doc.kb_id)
            if not kb or kb.deleted_at is not None:
                # EMBEDDING 已提交：同上，避免永久卡在 EMBEDDING
                raise ValueError("知识库不存在或已删除")

            run_ingest_pipeline(
                db,
                doc=doc,
                kb=kb,
                data=IngestInput(
                    filename=doc.filename,
                    mime_type=doc.mime_type,
                    object_key=doc.object_key,
                    object_bucket=doc.object_bucket,
                    chunk_size=kb.chunk_size,
                    chunk_overlap=kb.chunk_overlap,
                ),
                embed_texts=embed_texts_for_kb_sync,
                embed_visual_chunks=embed_image_chunks_vectors_sync,
                raw=raw,
                on_before_index=clear_document_derived_data_sync,
            )

            doc.status = DocumentStatus.READY
            doc.fail_reason = None
    except Exception as exc:
        with get_sync_db() as db:
            doc = db.get(Document, doc_uuid)
            if doc and doc.deleted_at is None:
                persist_document_ingest_failure(db, doc, phase=phase, exc=exc)
        raise
