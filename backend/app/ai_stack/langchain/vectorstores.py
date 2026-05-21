"""LangChain 向量检索适配：底层仍为 Weaviate 封装。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.documents import Document

from app.ai_stack.langchain.embeddings import embed_query


def _search_vectors(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
    from app.core.weaviate_store import search_vectors

    return search_vectors(*args, **kwargs)


def hit_to_document(hit: dict[str, Any]) -> Document:
    return Document(
        page_content=hit.get("content_preview") or "",
        metadata={
            "score": hit.get("score"),
            "chunk_id": hit.get("chunk_id"),
            "document_id": hit.get("document_id"),
            "weaviate_uuid": hit.get("weaviate_uuid"),
        },
    )


def search_kb(
    query: str,
    *,
    tenant_id: UUID,
    kb_id: UUID,
    limit: int = 10,
) -> list[dict[str, Any]]:
    vector = embed_query(query)
    return _search_vectors(
        vector,
        tenant_id=tenant_id,
        kb_id=kb_id,
        limit=limit,
    )


def search_multi_kb(
    query: str,
    *,
    tenant_id: UUID,
    kb_ids: list[str] | list[UUID],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """多知识库检索并合并排序（保持与原业务相同的 dict 结构）。"""
    if not kb_ids:
        return []
    vector = embed_query(query)
    all_hits: list[dict[str, Any]] = []
    for kid in kb_ids:
        hits = _search_vectors(
            vector,
            tenant_id=tenant_id,
            kb_id=UUID(str(kid)),
            limit=top_k,
        )
        all_hits.extend(hits)
    all_hits.sort(key=lambda h: h.get("score", 0), reverse=True)
    return all_hits[:top_k]


def search_as_documents(
    query: str,
    *,
    tenant_id: UUID,
    kb_ids: list[str] | list[UUID],
    top_k: int = 5,
) -> list[Document]:
    return [hit_to_document(h) for h in search_multi_kb(
        query, tenant_id=tenant_id, kb_ids=kb_ids, top_k=top_k
    )]
