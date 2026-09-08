"""
LangChain 向量检索适配层（L3，纯转发壳）。

职责
----
- 将 **query 文本** 检索委托 **L2** ``rag.retrieve.multi_kb`` 做 vector/hybrid/rerank 召回。
- embed/rerank 回调经 ``KbRetrievalBindings`` 由 L1 装配注入（本层不感知租户模型解析）。
- 不承担 ``kb_search_logs`` 审计写入（由 L1 检索调用方负责）。

使用约定
--------
Agent、流程节点、内置工具应 import 本模块或 ``rag.generate``，
勿直接操作 ``infra.vector_store`` 或手写 Filter 表达式。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.integrations.langchain.kb_retrieval import KbRetrievalBindings
from app.models.kb import KnowledgeBase
from app.rag.retrieve.multi_kb import search_kb as _search_kb
from app.rag.retrieve.multi_kb import search_multi_kb_async as _search_multi_kb_async


def search_kb(
    query: str,
    *,
    kb: KnowledgeBase,
    db: Session,
    limit: int = 10,
    mode: str = "default",
    bindings: KbRetrievalBindings,
) -> list[dict[str, Any]]:
    """单 KB 同步检索（绑定由调用方注入，供 embed/rerank）。"""
    return _search_kb(
        query,
        kb=kb,
        db=db,
        limit=limit,
        mode=mode,
        embed_query_sync=bindings.embed_query_sync,
        resolve_rerank_sync=bindings.resolve_rerank_sync,
    )


async def search_multi_kb_async(
    query: str,
    *,
    kbs: list[KnowledgeBase],
    db: AsyncSession,
    tenant_id: UUID,
    top_k: int = 5,
    mode: str = "default",
    bindings: KbRetrievalBindings,
) -> list[dict[str, Any]]:
    """多 KB 异步检索（embed/rerank 由 bindings 注入；审计日志由 L1 检索 API 自行负责）。"""
    return await _search_multi_kb_async(
        query,
        kbs=kbs,
        db=db,
        tenant_id=tenant_id,
        top_k=top_k,
        mode=mode,
        embed_query=bindings.embed_query,
        resolve_rerank=bindings.resolve_rerank,
    )
