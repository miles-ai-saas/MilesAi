"""LangChain 向量检索适配：检索向量按知识库绑定的 ModelConfig 生成。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.documents import Document
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.ai_stack.langchain.embeddings import embed_query_for_kb, embed_query_for_kb_sync
from app.infra.vector_store import search_vectors as _search_vectors
from app.models.kb import KnowledgeBase


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
    db: Session,
    limit: int = 10,
) -> list[dict[str, Any]]:
    vector = embed_query_for_kb_sync(db, kb, query)
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
    db: Session,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """多知识库检索（同步，Worker / 工具链）。"""
    if not kbs:
        return []
    all_hits: list[dict[str, Any]] = []
    for kb in kbs:
        hits = search_kb(query, kb=kb, db=db, limit=top_k)
        all_hits.extend(hits)
    all_hits.sort(key=lambda h: h.get("score", 0), reverse=True)
    return all_hits[:top_k]


async def search_multi_kb_async(
    query: str,
    *,
    kbs: list[KnowledgeBase],
    db: AsyncSession,
    tenant_id: UUID,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """多知识库检索（异步，RAG / API）。"""
    if not kbs:
        return []
    all_hits: list[dict[str, Any]] = []
    for kb in kbs:
        vector = await embed_query_for_kb(db, tenant_id, kb, query)
        hits = _search_vectors(
            vector,
            tenant_id=kb.tenant_id,
            kb_id=kb.id,
            limit=top_k,
        )
        all_hits.extend(hits)
    all_hits.sort(key=lambda h: h.get("score", 0), reverse=True)
    return all_hits[:top_k]


def search_as_documents(
    query: str,
    *,
    kbs: list[KnowledgeBase],
    db: Session,
    top_k: int = 5,
) -> list[Document]:
    return [hit_to_document(h) for h in search_multi_kb(query, kbs=kbs, db=db, top_k=top_k)]
