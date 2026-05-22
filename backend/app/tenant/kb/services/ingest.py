"""文档入库流水线（供 Celery Worker 同步调用）。"""

from uuid import UUID

from app.ai.chunking import split_text
from app.ai_stack.langchain.embeddings import embed_texts_for_kb_sync
from app.ai.media import vector_type_for_document
from app.ai.parsers import parse_file
from app.deletion.document import clear_document_derived_data_sync
from app.infra.db import get_sync_db
from app.infra.storage import download_bytes
from app.infra.vector_store import upsert_chunk_vector
from app.models.kb import Document, DocumentChunk, DocumentStatus, KnowledgeBase, VectorRef


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

            raw = download_bytes(doc.object_key, doc.object_bucket)
            text = parse_file(raw, doc.filename, doc.mime_type)
            chunks_text = split_text(text, kb.chunk_size, kb.chunk_overlap)
            if not chunks_text:
                raise ValueError("未能提取有效文本")

            current_phase = DocumentStatus.EMBEDDING
            doc.status = DocumentStatus.EMBEDDING
            db.flush()

            clear_document_derived_data_sync(db, doc.id)
            vectors = embed_texts_for_kb_sync(db, kb, chunks_text)
            vector_type = vector_type_for_document(doc.filename, doc.mime_type)

            for idx, (content, vector) in enumerate(zip(chunks_text, vectors)):
                chunk = DocumentChunk(
                    tenant_id=doc.tenant_id,
                    document_id=doc.id,
                    kb_id=doc.kb_id,
                    chunk_index=idx,
                    content=content,
                )
                db.add(chunk)
                db.flush()

                ext_vector_id = upsert_chunk_vector(
                    vector=vector,
                    tenant_id=doc.tenant_id,
                    kb_id=doc.kb_id,
                    document_id=doc.id,
                    chunk_id=chunk.id,
                    content_preview=content,
                    object_key=doc.object_key,
                )
                db.add(
                    VectorRef(
                        tenant_id=doc.tenant_id,
                        chunk_id=chunk.id,
                        vector_id=ext_vector_id,
                        vector_type=vector_type,
                    )
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
