"""文档入库管道（Parse → Chunk → Embed → Index）。

L2 同步管道；状态机与 Celery 入口在 tenant.kb.services.ingest。
每分片：先落 PG（chunk + vector_ref），再 upsert 向量库，保证 chunk_id 可用于向量 external_id。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.kb import Document, DocumentChunk, KnowledgeBase, VectorRef
from app.rag.chunk import chunk_documents
from app.rag.index.gateway import upsert_chunk_vector
from app.rag.parse import vector_type_for_document
from app.rag.parse.loaders import load_documents_from_bytes


class EmbedTextsForKb(Protocol):
    def __call__(
        self, db: Session, kb: KnowledgeBase, texts: list[str]
    ) -> list[list[float]]: ...


class LoadObjectBytes(Protocol):
    def __call__(self, object_key: str, object_bucket: str) -> bytes: ...


@dataclass(frozen=True)
class IngestInput:
    filename: str
    mime_type: str
    object_key: str
    object_bucket: str
    chunk_size: int
    chunk_overlap: int


@dataclass
class IngestResult:
    chunks_text: list[str]
    chunk_count: int


def run_ingest_pipeline(
    db: Session,
    *,
    doc: Document,
    kb: KnowledgeBase,
    data: IngestInput,
    embed_texts: EmbedTextsForKb,
    load_bytes: LoadObjectBytes,
    on_before_index: Callable[[Session, UUID], None] | None = None,
) -> IngestResult:
    """
    同步执行入库管道（不含文档状态机）。
    load_bytes：从对象存储读取原始文件（通常为 download_bytes）。
    on_before_index：写入新分片前清理旧 chunk/向量（通常为 clear_document_derived_data_sync）。
    """
    raw = load_bytes(data.object_key, data.object_bucket)
    docs = load_documents_from_bytes(raw, data.filename, data.mime_type)
    chunks = chunk_documents(docs, data.chunk_size, data.chunk_overlap)
    if not chunks:
        raise ValueError("未能提取有效文本")

    # 重试/覆盖入库：先删旧 chunk、vector_ref 与向量库记录
    if on_before_index is not None:
        on_before_index(db, doc.id)

    chunks_text = [c.content for c in chunks]
    vectors = embed_texts(db, kb, chunks_text)
    vector_type = vector_type_for_document(data.filename, data.mime_type)

    for idx, (piece, vector) in enumerate(zip(chunks, vectors)):
        chunk = DocumentChunk(
            tenant_id=doc.tenant_id,
            document_id=doc.id,
            kb_id=doc.kb_id,
            chunk_index=idx,
            content=piece.content,
            page_no=piece.page_no,
        )
        db.add(chunk)
        db.flush()  # 需要 chunk.id 再写向量库

        ext_vector_id = upsert_chunk_vector(
            vector=vector,
            tenant_id=doc.tenant_id,
            kb_id=doc.kb_id,
            document_id=doc.id,
            chunk_id=chunk.id,
            content_preview=piece.content,
            object_key=data.object_key,
            page_no=piece.page_no,
        )
        db.add(
            VectorRef(
                tenant_id=doc.tenant_id,
                chunk_id=chunk.id,
                vector_id=ext_vector_id,
                vector_type=vector_type,
            )
        )

    return IngestResult(chunks_text=chunks_text, chunk_count=len(chunks_text))
