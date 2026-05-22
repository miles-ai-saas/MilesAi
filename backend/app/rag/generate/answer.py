"""RAG 检索增强生成（线性路径，无 LangGraph）。

多 KB 检索经 integrations.langchain.vectorstores → rag.retrieve.multi_kb。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext
from app.integrations.langchain.chat_models import ainvoke_chat
from app.integrations.langchain.vectorstores import search_multi_kb_async
from app.models.model import ModelConfig
from app.rag.generate.context import build_rag_user_prompt
from app.rag.load import load_kbs_for_tenant


async def retrieve_hits(
    query: str,
    *,
    tenant_id: UUID,
    kb_ids: list[str],
    db: AsyncSession,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    kbs = await load_kbs_for_tenant(db, tenant_id, kb_ids)
    return await search_multi_kb_async(
        query, kbs=kbs, db=db, tenant_id=tenant_id, top_k=top_k
    )


async def retrieve_hits_with_ctx(
    query: str,
    *,
    ctx: TenantContext,
    kb_ids: list[str],
    db: AsyncSession,
    top_k: int = 5,
    agent_id: UUID | None = None,
) -> list[dict[str, Any]]:
    kbs = await load_kbs_for_tenant(db, ctx.tenant_id, kb_ids)
    return await search_multi_kb_async(
        query,
        kbs=kbs,
        db=db,
        tenant_id=ctx.tenant_id,
        top_k=top_k,
        actor_user_id=ctx.user_id,
        agent_id=agent_id,
    )


async def rag_answer(
    *,
    model: ModelConfig,
    system_prompt: str,
    query: str,
    kb_ids: list[str],
    tenant_id: UUID,
    db: AsyncSession,
    top_k: int = 5,
    temperature: float = 0.7,
) -> tuple[str, list[dict[str, Any]]]:
    """检索增强问答，返回 (answer, hits)。"""
    hits = await retrieve_hits(
        query,
        tenant_id=tenant_id,
        kb_ids=kb_ids,
        db=db,
        top_k=top_k,
    )
    if not hits:
        prompt = f"{system_prompt}\n\n用户问题：{query}"
    else:
        prompt = build_rag_user_prompt(
            system_prompt=system_prompt,
            query=query,
            hits=hits,
        )
    answer = await ainvoke_chat(
        model,
        [{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return answer, hits
