"""知识库检索日志写入。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_search_log import KbSearchLog

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
    retrieval_mode: str = "vector",
) -> None:
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
