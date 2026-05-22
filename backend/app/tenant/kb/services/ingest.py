"""文档入库（Celery）：状态机 + 调用 rag.pipeline。

PARSING/EMBEDDING 在 Worker 内顺序执行；失败时按 current_phase 区分 parse_failed / embed_failed。
"""

from uuid import UUID

from app.deletion.document import clear_document_derived_data_sync
from app.infra.db import get_sync_db
from app.infra.storage import download_bytes
from app.integrations.langchain.embeddings import embed_texts_for_kb_sync
from app.models.kb import Document, DocumentStatus, KnowledgeBase
from app.rag.pipeline import IngestInput, run_ingest_pipeline


def run_ingest(document_id: str) -> None:
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
            doc.status = (
                DocumentStatus.EMBED_FAILED
                if current_phase == DocumentStatus.EMBEDDING
                else DocumentStatus.PARSE_FAILED
            )
            doc.fail_reason = str(exc)[:2000]
            db.flush()
            raise
