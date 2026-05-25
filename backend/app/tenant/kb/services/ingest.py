"""文档入库（Celery）：状态机 + 调用 rag.pipeline。

链路：ingest_document → run_ingest → run_ingest_pipeline
     （download → parse → chunk → embed → PG chunk + 向量库 upsert）。
PARSING/EMBEDDING 在 Worker 内顺序推进；失败按 current_phase 写 PARSE_FAILED / EMBED_FAILED。
异常时 persist_document_ingest_failure 须先 commit，避免 get_sync_db rollback 吞状态。
"""

from uuid import UUID

from app.deletion.document import clear_document_derived_data_sync
from app.infra.db import get_sync_db
from app.infra.storage import download_bytes
from app.integrations.langchain.embeddings import embed_texts_for_kb_sync
from app.models.kb import Document, DocumentStatus, KnowledgeBase
from app.rag.pipeline import IngestInput, run_ingest_pipeline
from app.tenant.kb.services.ingest_failure import persist_document_ingest_failure


def run_ingest(document_id: str) -> None:
    """同步执行单文档入库（由 Celery Worker 调用，非 HTTP 直连）。"""
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

            # 实际 parse+chunk+embed 均在 pipeline 内同步完成；EMBEDDING 表示向量化阶段
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
                load_bytes=download_bytes,
                on_before_index=clear_document_derived_data_sync,
            )

            doc.status = DocumentStatus.READY
            doc.fail_reason = None
            db.flush()
        except Exception as exc:
            persist_document_ingest_failure(db, doc, phase=current_phase, exc=exc)
            raise
