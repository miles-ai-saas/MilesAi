"""
知识库检索审计日志（表 ``kb_search_logs``）。

写入方
------
- kb 服务检索入口 ``app/tenant/kb/services/kb/search.py`` 的
  ``KnowledgeBaseService.search``（source=api）

B-2b 收敛后，L3 ``vectorstores`` 检索壳与 L2 ``multi_kb`` 不再承担
``kb_search_logs`` 写入；当前写表统一收敛在 kb 服务检索入口。

用于监控检索延迟、命中数、实际 retrieval_mode（含 +rerank 后缀）。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_ai.rag.retrieve.constants import RETRIEVAL_VECTOR
from miles_core.models.kb.search_log import KbSearchLog

_QUERY_MAX_LEN = 2000


async def write_kb_search_log(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    query: str,
    top_k: int,
    hit_count: int,
    latency_ms: int,
    source: str = "api",
    kb_id: UUID | None = None,
    kb_ids: list[str] | None = None,
    actor_user_id: UUID | None = None,
    agent_id: UUID | None = None,
    request_id: str | None = None,
    retrieval_mode: str = RETRIEVAL_VECTOR,
) -> None:
    """写入 kb_search_logs；query 超长截断至 2000 字符。"""
    q = query if len(query) <= _QUERY_MAX_LEN else query[:_QUERY_MAX_LEN]
    log = KbSearchLog(
        tenant_id=tenant_id,
        kb_id=kb_id,
        kb_ids=kb_ids,
        query=q,
        top_k=top_k,
        hit_count=hit_count,
        latency_ms=latency_ms,
        retrieval_mode=retrieval_mode,
        source=source,
        actor_user_id=actor_user_id,
        agent_id=agent_id,
        request_id=request_id,
    )
    db.add(log)
    await db.flush()
