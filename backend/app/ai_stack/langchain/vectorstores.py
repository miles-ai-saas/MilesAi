"""LangChain 向量检索适配：检索向量按知识库绑定的 ModelConfig 生成。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.documents import Document
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.ai_stack.langchain.embeddings import embed_query_for_kb, embed_query_for_kb_sync
from app.models.kb import KnowledgeBase
from app.tenant.kb.services.retrieval import (
    resolve_retrieval_mode,
    search_kb_chunks,
    search_kb_chunks_sync,
)


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
    mode: str = "default",
) -> list[dict[str, Any]]:
    vector = embed_query_for_kb_sync(db, kb, query)
    return search_kb_chunks_sync(
        db,
        kb=kb,
        query=query,
        query_vector=vector,
        limit=limit,
        mode=mode,
    )


def search_multi_kb(
    query: str,
    *,
    kbs: list[KnowledgeBase],
    db: Session,
    top_k: int = 5,
    mode: str = "default",
) -> list[dict[str, Any]]:
    """多知识库检索（同步，Worker / 工具链）。"""
    if not kbs:
        return []
    all_hits: list[dict[str, Any]] = []
    for kb in kbs:
        hits = search_kb(query, kb=kb, db=db, limit=top_k, mode=mode)
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
    mode: str = "default",
    source: str = "agent",
    actor_user_id: UUID | None = None,
    agent_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """多知识库检索（异步，RAG / API）。"""
    import time

    from app.tenant.kb.services.search_log import write_kb_search_log

    if not kbs:
        return []
    started = time.perf_counter()
    all_hits: list[dict[str, Any]] = []
    modes_used: list[str] = []
    for kb in kbs:
        vector = await embed_query_for_kb(db, tenant_id, kb, query)
        modes_used.append(resolve_retrieval_mode(kb, mode))
        hits = await search_kb_chunks(
            db,
            kb=kb,
            query=query,
            query_vector=vector,
            limit=top_k,
            mode=mode,
        )
        all_hits.extend(hits)
    all_hits.sort(key=lambda h: h.get("score", 0), reverse=True)
    result = all_hits[:top_k]
    latency_ms = int((time.perf_counter() - started) * 1000)
    log_mode = "hybrid" if "hybrid" in modes_used else "vector"
    await write_kb_search_log(
        db,
        tenant_id=tenant_id,
        kb_id=kbs[0].id if len(kbs) == 1 else None,
        kb_ids=[str(k.id) for k in kbs] if len(kbs) != 1 else None,
        query=query,
        top_k=top_k,
        hit_count=len(result),
        latency_ms=latency_ms,
        source=source,
        actor_user_id=actor_user_id,
        agent_id=agent_id,
        retrieval_mode=log_mode,
    )
    return result


def search_as_documents(
    query: str,
    *,
    kbs: list[KnowledgeBase],
    db: Session,
    top_k: int = 5,
) -> list[Document]:
    return [hit_to_document(h) for h in search_multi_kb(query, kbs=kbs, db=db, top_k=top_k)]
