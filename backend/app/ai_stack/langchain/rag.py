"""LangChain RAG 链路：检索 + 上下文拼装 + 生成。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_stack.langchain.chat_models import ainvoke_chat
from app.ai_stack.langchain.vectorstores import search_multi_kb
from app.core.tenant import TenantContext
from app.models.model import ModelConfig
from app.tenant.kb.services.kb_load import load_kbs_for_tenant


def format_hits_context(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return ""
    return "\n\n".join(
        f"[{h.get('score', 0):.2f}] {h.get('content_preview', '')}" for h in hits
    )


def build_rag_user_prompt(
    *,
    system_prompt: str,
    query: str,
    hits: list[dict[str, Any]],
) -> str:
    context = format_hits_context(hits)
    return f"{system_prompt}\n\n参考内容：\n{context}\n\n用户问题：{query}"


async def retrieve_hits(
    query: str,
    *,
    tenant_id: UUID,
    kb_ids: list[str],
    db: AsyncSession,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    kbs = await load_kbs_for_tenant(db, tenant_id, kb_ids)
    return search_multi_kb(query, kbs=kbs, top_k=top_k)


async def retrieve_hits_with_ctx(
    query: str,
    *,
    ctx: TenantContext,
    kb_ids: list[str],
    db: AsyncSession,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    return await retrieve_hits(
        query, tenant_id=ctx.tenant_id, kb_ids=kb_ids, db=db, top_k=top_k
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
