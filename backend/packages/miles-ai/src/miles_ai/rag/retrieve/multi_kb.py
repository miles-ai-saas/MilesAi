"""
KB 检索实现（L2）：同步单 KB ``search_kb``、异步多 KB ``search_multi_kb_async``。

行为
----
- 每个 KB **独立** ``embed_query``（embedding 模型/维度可能不同，不可共用一条 query 向量）。
- 每个 KB 调用 ``search_kb_chunks``（vector/hybrid/rerank 按 KB 配置）。
- 合并所有 hit 后按 ``score`` 全局降序，截断 ``top_k``。

同步 ``search_kb`` 由 L3 ``vectorstores`` 壳转发（内置工具用）；
异步 ``search_multi_kb_async`` 经 L3 壳注入 bindings 供问答/检索链路用。
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from miles_core.models.kb import KnowledgeBase
from miles_core.models.model import ModelConfig
from miles_ai.rag.retrieve.retriever import (
    resolve_retrieval_mode,
    search_kb_chunks,
    search_kb_chunks_sync,
)

SearchLogHook = Callable[
    [AsyncSession, dict[str, Any]],
    Awaitable[None],
]

EmbedQuerySync = Callable[[Session, KnowledgeBase, str], list[float]]
EmbedQueryAsync = Callable[
    [AsyncSession, UUID, KnowledgeBase, str],
    Awaitable[list[float]],
]
ResolveRerankSync = Callable[[Session, KnowledgeBase, UUID], ModelConfig | None]
ResolveRerankAsync = Callable[
    [AsyncSession, KnowledgeBase, UUID],
    Awaitable[ModelConfig | None],
]


def search_kb(
    query: str,
    *,
    kb: KnowledgeBase,
    db: Session,
    limit: int = 10,
    mode: str = "default",
    embed_query_sync: EmbedQuerySync,
    resolve_rerank_sync: ResolveRerankSync | None = None,
) -> list[dict[str, Any]]:
    """单 KB 同步检索（注入 embed 与 rerank 解析回调）。"""
    vector = embed_query_sync(db, kb, query)
    rerank_model = None
    if resolve_rerank_sync is not None and kb.rerank_model_config_id:
        rerank_model = resolve_rerank_sync(db, kb, kb.tenant_id)
    return search_kb_chunks_sync(
        db,
        kb=kb,
        query=query,
        query_vector=vector,
        limit=limit,
        mode=mode,
        rerank_model=rerank_model,
    )


async def search_multi_kb_async(
    query: str,
    *,
    kbs: list[KnowledgeBase],
    db: AsyncSession,
    tenant_id: UUID,
    top_k: int = 5,
    mode: str = "default",
    embed_query: EmbedQueryAsync,
    resolve_rerank: ResolveRerankAsync | None = None,
    on_complete: SearchLogHook | None = None,
    source: str = "agent",
    actor_user_id: UUID | None = None,
    agent_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """异步多 KB 检索；可选 on_complete 写审计日志。"""
    if not kbs:
        return []
    started = time.perf_counter()
    all_hits: list[dict[str, Any]] = []
    modes_used: list[str] = []
    rerank_used = False
    for kb in kbs:
        vector = await embed_query(db, tenant_id, kb, query)
        modes_used.append(resolve_retrieval_mode(kb, mode))
        rerank_model = None
        if resolve_rerank is not None and kb.rerank_model_config_id:
            rerank_model = await resolve_rerank(db, kb, tenant_id)
            rerank_used = rerank_used or rerank_model is not None
        hits = await search_kb_chunks(
            db,
            kb=kb,
            query=query,
            query_vector=vector,
            limit=top_k,
            mode=mode,
            rerank_model=rerank_model,
        )
        all_hits.extend(hits)
    all_hits.sort(key=lambda h: h.get("score", 0), reverse=True)
    result = all_hits[:top_k]
    if on_complete is not None:
        latency_ms = int((time.perf_counter() - started) * 1000)
        log_mode = "hybrid" if "hybrid" in modes_used else "vector"
        if rerank_used:
            log_mode = f"{log_mode}+rerank"
        await on_complete(
            db,
            {
                "tenant_id": tenant_id,
                "kbs": kbs,
                "query": query,
                "top_k": top_k,
                "hit_count": len(result),
                "latency_ms": latency_ms,
                "retrieval_mode": log_mode,
                "source": source,
                "actor_user_id": actor_user_id,
                "agent_id": agent_id,
            },
        )
    return result
