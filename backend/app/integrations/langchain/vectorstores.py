"""
LangChain 向量检索适配层（L3）。

职责
----
- 将 **query 文本** 转为向量（``embed_query_for_kb*``，按 KB 的 embedding 模型）。
- 委托 **L2** ``rag.retrieve.multi_kb`` 做 vector/hybrid/rerank 召回。
- 可选写 ``kb_search_logs``（Agent 路径默认开启）。

使用约定
--------
Agent、流程节点、内置工具应 import 本模块或 ``rag.generate``，
勿直接操作 ``infra.vector_store`` 或手写 Filter 表达式。
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
    """解析 KB 绑定的 rerank 模型；未配置则跳过重排。"""
    if not kb.rerank_model_config_id:
        return None
    return resolve_rerank_model_sync(db, kb.rerank_model_config_id, tenant_id)


async def _resolve_rerank_async(
    db: AsyncSession, kb: KnowledgeBase, tenant_id: UUID
) -> ModelConfig | None:
    """异步解析 rerank 模型（multi_kb_async 使用）。"""
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
    """单 KB 同步检索（注入 embed + rerank 解析）。"""
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
    """多 KB 同步检索后全局按 score 排序截断。"""
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
    """``search_multi_kb_async`` 完成后的审计回调。"""
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
    """
    Agent / 多 KB RAG 主入口。

    ``write_log=False`` 可用于内部探测；默认写 search_log 便于审计与监控。
    """
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
    """检索 hit 转为 LangChain Document，供工具链/Retriever 使用。"""
    return [hit_to_document(h) for h in search_multi_kb(query, kbs=kbs, db=db, top_k=top_k)]
