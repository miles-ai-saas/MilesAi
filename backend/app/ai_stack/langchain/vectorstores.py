"""LangChain 向量检索适配：检索向量按知识库 embedding 规格生成。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.documents import Document

from app.ai_stack.langchain.embeddings import embed_query_for_kb
from app.models.kb import KnowledgeBase
from app.infra.vector_store import search_vectors as _search_vectors


def hit_to_document(hit: dict[str, Any]) -> Document:
    return Document(
        page_content=hit.get("content_preview") or "",
        metadata={
            "score": hit.get("score"),
            "chunk_id": hit.get("chunk_id"),
            "document_id": hit.get("document_id"),
            "vector_id": hit.get("vector_id"),
        },
    )


def search_kb(
    query: str,
    *,
    kb: KnowledgeBase,
    limit: int = 10,
) -> list[dict[str, Any]]:
    vector = embed_query_for_kb(kb, query)
    return _search_vectors(
        vector,
        tenant_id=kb.tenant_id,
        kb_id=kb.id,
        limit=limit,
    )


def search_multi_kb(
    query: str,
    *,
    kbs: list[KnowledgeBase],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """多知识库检索：每个 KB 使用各自 embedding 规格生成查询向量。"""
    if not kbs:
        return []
    all_hits: list[dict[str, Any]] = []
    for kb in kbs:
        hits = search_kb(query, kb=kb, limit=top_k)
        all_hits.extend(hits)
    all_hits.sort(key=lambda h: h.get("score", 0), reverse=True)
    return all_hits[:top_k]


def search_as_documents(
    query: str,
    *,
    kbs: list[KnowledgeBase],
    top_k: int = 5,
) -> list[Document]:
    return [hit_to_document(h) for h in search_multi_kb(query, kbs=kbs, top_k=top_k)]
