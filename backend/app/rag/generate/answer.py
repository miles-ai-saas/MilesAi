"""
RAG 检索增强生成（线性路径，无 LangGraph）。

适用场景
--------
- 简单「多 KB 问答」API 或脚本：retrieve → 拼 prompt → ``ainvoke_chat``。
- 复杂 Agent / 流程画布走 ``integrations.langchain`` / LangGraph，不经过本模块。

依赖
----
- 检索：``integrations.langchain.vectorstores.search_multi_kb_async`` → ``rag.retrieve.multi_kb``。
- 上下文：``generate.context.build_rag_user_prompt``。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas.media import MediaRefIn
from app.core.tenant import TenantContext
from app.integrations.chat.multimodal import build_invoke_messages_with_media
from app.integrations.langchain.chat_models import OnDelta, ainvoke_chat
from app.integrations.langchain.vectorstores import search_multi_kb_async
from app.integrations.litellm.usage_sink import UsageSink
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
    mode: str = "default",
) -> list[dict[str, Any]]:
    """
    多 KB 检索（LangGraph retrieve 节点、线性 RAG 共用）。

    ``write_log=False`` 等价路径：不记 actor/agent，不写 ``kb_search_logs``。
    需审计时请用 ``retrieve_hits_with_ctx``。
    """
    kbs = await load_kbs_for_tenant(db, tenant_id, kb_ids)
    return await search_multi_kb_async(
        query,
        kbs=kbs,
        db=db,
        tenant_id=tenant_id,
        top_k=top_k,
        mode=mode,
        write_log=False,
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
    """带租户用户/agent 的检索；完成后可写 search_log（由 vectorstores 回调）。"""
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
    media: list[MediaRefIn] | None = None,
    ctx: TenantContext | None = None,
    retrieve_query: str | None = None,
    on_delta: OnDelta | None = None,
    usage_sink: UsageSink | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """
    端到端 RAG：检索 → 拼 prompt → LLM 生成。

    ``model`` 由调用方 resolve（装配点语义，见 ``resolve_invoke_model``），
    直接用于生成；用量经 ``usage_sink`` 注入。
    ``retrieve_query`` 仅用于向量检索；``query`` 写入生成 prompt（可含「请根据附图回答」）。
    返回 (answer 文本, hits) 便于调用方展示引用来源。
    """
    search_q = (retrieve_query if retrieve_query is not None else query).strip()
    hits = await retrieve_hits(
        search_q,
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
    messages: list[dict[str, Any]]
    if media and ctx:
        messages = await build_invoke_messages_with_media(
            db,
            ctx,
            prompt_text=prompt,
            media=media,
        )
    else:
        messages = [{"role": "user", "content": prompt}]

    answer = await ainvoke_chat(
        model,
        messages,
        temperature=temperature,
        usage_sink=usage_sink,
        on_delta=on_delta,
    )
    return answer, hits
