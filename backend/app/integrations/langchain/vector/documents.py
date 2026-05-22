"""ChunkVectorRecord ↔ LangChain Document；检索 hit 转换。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.documents import Document

from app.core.config import get_settings
from app.infra.vector_store.base import ChunkVectorRecord

METADATA_TENANT_ID = "tenant_id"
METADATA_KB_ID = "kb_id"
METADATA_DOCUMENT_ID = "document_id"
METADATA_CHUNK_ID = "chunk_id"
METADATA_OBJECT_KEY = "object_key"
METADATA_PAGE_NO = "page_no"
METADATA_MODALITY = "modality"

TEXT_KEY = "content_preview"


def chunk_record_to_document(record: ChunkVectorRecord) -> Document:
    chunk_id = str(record.chunk_id)
    return Document(
        page_content=record.content_preview[:500],
        metadata={
            METADATA_TENANT_ID: str(record.tenant_id),
            METADATA_KB_ID: str(record.kb_id),
            METADATA_DOCUMENT_ID: str(record.document_id),
            METADATA_CHUNK_ID: chunk_id,
            METADATA_OBJECT_KEY: record.object_key,
            METADATA_PAGE_NO: record.page_no or 0,
            METADATA_MODALITY: "text",
        },
        id=record.external_id or chunk_id,
    )


def document_to_chunk_record(
    doc: Document,
    *,
    vector: list[float],
    tenant_id: UUID,
    kb_id: UUID,
    document_id: UUID,
) -> ChunkVectorRecord:
    meta = doc.metadata or {}
    chunk_id = UUID(str(meta.get(METADATA_CHUNK_ID) or doc.id))
    return ChunkVectorRecord(
        vector=vector,
        tenant_id=tenant_id,
        kb_id=kb_id,
        document_id=document_id,
        chunk_id=chunk_id,
        content_preview=doc.page_content,
        object_key=str(meta.get(METADATA_OBJECT_KEY, "")),
        page_no=int(meta.get(METADATA_PAGE_NO) or 0) or None,
        external_id=doc.id,
    )


def _doc_to_hit_row(doc: Document, *, score: float) -> dict[str, Any]:
    meta = doc.metadata or {}
    return {
        "vector_id": doc.id or meta.get("vector_id") or meta.get("uuid"),
        "chunk_id": meta.get(METADATA_CHUNK_ID),
        "document_id": meta.get(METADATA_DOCUMENT_ID),
        "content_preview": doc.page_content,
        "score": score,
        "score_vector": score,
        "score_keyword": meta.get("score_keyword"),
    }


def hit_to_document(hit: dict[str, Any]) -> Document:
    return Document(
        page_content=hit.get("content_preview") or "",
        metadata={
            "score": hit.get("score"),
            METADATA_CHUNK_ID: hit.get("chunk_id"),
            METADATA_DOCUMENT_ID: hit.get("document_id"),
            "vector_id": hit.get("vector_id"),
            "score_vector": hit.get("score_vector"),
            "score_keyword": hit.get("score_keyword"),
        },
        id=str(hit.get("vector_id") or hit.get("chunk_id") or ""),
    )


def documents_to_hits(docs: list[Document]) -> list[dict[str, Any]]:
    return [_doc_to_hit_row(d, score=float((d.metadata or {}).get("score") or 0)) for d in docs]


def distance_pairs_to_hits(pairs: list[tuple[Document, float]]) -> list[dict[str, Any]]:
    return [
        _doc_to_hit_row(doc, score=float(1.0 - dist) if dist is not None else 0.0)
        for doc, dist in pairs
    ]


def scored_pairs_to_hits(pairs: list[tuple[Document, float]]) -> list[dict[str, Any]]:
    return [
        _doc_to_hit_row(doc, score=float(score) if score is not None else 0.0)
        for doc, score in pairs
    ]


def milvus_filter_expr(tenant_id: UUID, kb_id: UUID | None) -> str:
    expr = f'tenant_id == "{tenant_id}"'
    if kb_id:
        expr += f' and kb_id == "{kb_id}"'
    return expr


def pg_metadata_filter(tenant_id: UUID, kb_id: UUID | None) -> dict[str, str]:
    filt: dict[str, str] = {METADATA_TENANT_ID: str(tenant_id)}
    if kb_id:
        filt[METADATA_KB_ID] = str(kb_id)
    return filt


def known_embedding_dimensions() -> list[int]:
    base = [get_settings().embedding_vector_dimension, 768, 1024]
    return list(dict.fromkeys(base))
