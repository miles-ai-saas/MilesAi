"""LangChain 向量检索适配（L3）：按 KB 生成 query 向量后委托 rag.retrieve.multi_kb。

Agent/流程/工具应优先本模块或 rag.generate.retrieve_hits，勿直接拼向量库 Filter。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.documents import Document
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.integrations.langchain.embeddings import embed_query_for_kb, embed_query_for_kb_sync
from app.integrations.langchain.vector.documents import hit_to_document
from app.models.kb import KnowledgeBase
from app.models.model import ModelConfig
from app.rag.retrieve.multi_kb import search_kb as _search_kb
from app.rag.retrieve.multi_kb import search_multi_kb as _search_multi_kb
from app.rag.retrieve.multi_kb import search_multi_kb_async as _search_multi_kb_async
from app.tenant.models.services.rerank_resolve import (
    resolve_rerank_model_by_id,
    resolve_rerank_model_sync,
)


def _resolve_rerank_sync(db: Session, kb: KnowledgeBase, tenant_id: UUID) -> ModelConfig | None:
    if not kb.rerank_model_config_id:
        return None
    return resolve_rerank_model_sync(db, kb.rerank_model_config_id, tenant_id)


async def _resolve_rerank_async(
    db: AsyncSession, kb: KnowledgeBase, tenant_id: UUID
) -> ModelConfig | None:
    if not kb.rerank_model_config_id:
        return None
    return await resolve_rerank_model_by_id(db, kb.rerank_model_config_id, tenant_id)


def search_kb(
    query: str,
    *,
    kb: KnowledgeBase,
    db: Session,
    limit: int = 10,
    mode: str = "default",
) -> list[dict[str, Any]]:
    return _search_kb(
        query,
        kb=kb,
        db=db,
        limit=limit,
        mode=mode,
        embed_query_sync=embed_query_for_kb_sync,
        resolve_rerank_sync=_resolve_rerank_sync,
    )


def search_multi_kb(
    query: str,
    *,
    kbs: list[KnowledgeBase],
    db: Session,
    top_k: int = 5,
    mode: str = "default",
) -> list[dict[str, Any]]:
    return _search_multi_kb(
        query,
        kbs=kbs,
        db=db,
        top_k=top_k,
        mode=mode,
        embed_query_sync=embed_query_for_kb_sync,
        resolve_rerank_sync=_resolve_rerank_sync,
    )


async def _write_search_log(db: AsyncSession, payload: dict[str, Any]) -> None:
    from app.tenant.kb.services.search_log import write_kb_search_log

    kbs: list[KnowledgeBase] = payload["kbs"]
    await write_kb_search_log(
        db,
        tenant_id=payload["tenant_id"],
        kb_id=kbs[0].id if len(kbs) == 1 else None,
        kb_ids=[str(k.id) for k in kbs] if len(kbs) != 1 else None,
        query=payload["query"],
        top_k=payload["top_k"],
        hit_count=payload["hit_count"],
        latency_ms=payload["latency_ms"],
        source=payload.get("source", "agent"),
        actor_user_id=payload.get("actor_user_id"),
        agent_id=payload.get("agent_id"),
        retrieval_mode=payload["retrieval_mode"],
    )


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
    write_log: bool = True,
) -> list[dict[str, Any]]:
    return await _search_multi_kb_async(
        query,
        kbs=kbs,
        db=db,
        tenant_id=tenant_id,
        top_k=top_k,
        mode=mode,
        embed_query=embed_query_for_kb,
        resolve_rerank=_resolve_rerank_async,
        on_complete=_write_search_log if write_log else None,
        source=source,
        actor_user_id=actor_user_id,
        agent_id=agent_id,
    )


def search_as_documents(
    query: str,
    *,
    kbs: list[KnowledgeBase],
    db: Session,
    top_k: int = 5,
) -> list[Document]:
    return [hit_to_document(h) for h in search_multi_kb(query, kbs=kbs, db=db, top_k=top_k)]
