"""
文档入库编排（Celery Worker 同步执行）。

分层
----
- **L1 本模块**：文档状态机（PENDING → PARSING → EMBEDDING → READY/失败）、
  注入存储/embedding 回调、调用 ``rag.pipeline.run_ingest_pipeline``。
- **L2 pipeline**：Parse → Chunk → Embed → ``gateway.upsert_chunk_vector``（见 rag 注释）。

调用链
------
``KnowledgeBaseService.upload_document`` → ``ingest_document.delay``
  → ``run_ingest``（本模块）→ ``run_ingest_pipeline``

状态说明
--------
PARSING/EMBEDDING 在 Worker 内顺序更新，便于前端展示进度；
实际 parse+chunk+embed 均在 pipeline 一次调用内完成，并非两个独立 Celery 子任务。

失败处理
----------
异常时 ``persist_document_ingest_failure`` **必须先 commit**，否则 ``get_sync_db``
上下文退出 rollback 会吞掉 PARSE_FAILED/EMBED_FAILED 状态。
"""

from uuid import UUID

from miles_portal.deletion.document import clear_document_derived_data_sync
from miles_core.infra.db import get_sync_db
from miles_core.infra.storage import download_bytes
from miles_core.models.kb import Document, DocumentStatus, KnowledgeBase
from miles_ai.rag.pipeline import IngestInput, run_ingest_pipeline
from miles_portal.tenant.kb.services.embeddings import (
    embed_image_chunks_vectors_sync,
    embed_texts_for_kb_sync,
)
from miles_portal.tenant.kb.services.ingest_failure import persist_document_ingest_failure


def run_ingest(document_id: str) -> None:
    """
    同步执行单文档入库（仅由 Celery Worker 调用，HTTP 不直连）。

    ``on_before_index=clear_document_derived_data_sync``：覆盖/重试入库前删除旧分片与向量。
    """
    with get_sync_db() as db:
        doc = db.get(Document, UUID(document_id))
        if not doc or doc.deleted_at is not None:
            return
        kb = db.get(KnowledgeBase, doc.kb_id)
        if not kb or kb.deleted_at is not None:
            return

        current_phase = DocumentStatus.PARSING
        try:
            doc.status = DocumentStatus.PARSING
            doc.fail_reason = None
            db.flush()

            # 进入 EMBEDDING 阶段（向量化+写向量库均在 pipeline 内完成）
            current_phase = DocumentStatus.EMBEDDING
            doc.status = DocumentStatus.EMBEDDING
            db.flush()

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
                load_bytes=lambda key, bucket: download_bytes(key, bucket, tenant_id=doc.tenant_id, db=db),
                on_before_index=clear_document_derived_data_sync,
            )

            doc.status = DocumentStatus.READY
            doc.fail_reason = None
            db.flush()
        except Exception as exc:
            persist_document_ingest_failure(db, doc, phase=current_phase, exc=exc)
            raise
