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

有附图但未传 ``media_reader`` 时显式 ``BadRequestError``，避免静默丢图。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_ai.integrations.chat.multimodal import build_invoke_messages_with_media
from miles_ai.integrations.langchain.chat_models import OnDelta, ainvoke_chat
from miles_ai.integrations.langchain.kb_retrieval import KbRetrievalBindings
from miles_ai.integrations.langchain.vectorstores import search_multi_kb_async
from miles_ai.integrations.litellm.usage_sink import UsageSink
from miles_ai.rag.generate.context import build_rag_user_prompt
from miles_ai.rag.load import load_kbs_for_tenant
from miles_common.exceptions import BadRequestError
from miles_common.schemas.media import MediaRefIn
from miles_core.models.media.reader import MediaReader
from miles_core.models.model import ModelConfig


async def retrieve_hits(
    query: str,
    *,
    tenant_id: UUID,
    kb_ids: list[str],
    db: AsyncSession,
    top_k: int = 5,
    mode: str = "default",
    bindings: KbRetrievalBindings | None = None,
) -> list[dict[str, Any]]:
    """
    多 KB 检索（LangGraph retrieve 节点、线性 RAG 共用）。

    ``bindings`` 由 L1 装配注入，为 None 时抛 ValueError；
    本模块不写 ``kb_search_logs``（审计写入收敛在 L1 kb 服务检索入口）。
    """
    kbs = await load_kbs_for_tenant(db, tenant_id, kb_ids)
    if bindings is None:
        raise ValueError("检索链路缺少 KB 检索绑定（bindings），需由 L1 装配")
    return await search_multi_kb_async(
        query,
        kbs=kbs,
        db=db,
        tenant_id=tenant_id,
        top_k=top_k,
        mode=mode,
        bindings=bindings,
    )


def build_rag_prompt(*, system_prompt: str, query: str, hits: list[dict[str, Any]]) -> str:
    """按是否有命中拼接生成用 prompt（无命中时不带参考片段）。"""
    if not hits:
        return f"{system_prompt}\n\n用户问题：{query}"
    return build_rag_user_prompt(system_prompt=system_prompt, query=query, hits=hits)


async def generate_rag_answer(
    *,
    model: ModelConfig,
    prompt: str,
    media: list[MediaRefIn] | None = None,
    media_reader: MediaReader | None = None,
    temperature: float = 0.7,
    on_delta: OnDelta | None = None,
    usage_sink: UsageSink | None = None,
) -> str:
    """生成阶段：附图解析 + ``ainvoke_chat``。**不接收 db**。

    检索已由调用方（L1）在短会话内完成，hits 拼进 ``prompt``；本函数因此可以
    在「连接已归还池」的状态下运行——这是「生成期间不持有连接」的结构性保证，
    签名里没有 db 是刻意的，请勿为了方便再加回来。
    """
    messages: list[dict[str, Any]]
    if media:
        if media_reader is None:
            raise BadRequestError("媒体读取器未装配（media_reader），无法解析附图")
        messages = await build_invoke_messages_with_media(
            media_reader,
            prompt_text=prompt,
            media=media,
        )
    else:
        messages = [{"role": "user", "content": prompt}]
    return await ainvoke_chat(
        model,
        messages,
        temperature=temperature,
        usage_sink=usage_sink,
        on_delta=on_delta,
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
    media_reader: MediaReader | None = None,
    retrieve_query: str | None = None,
    on_delta: OnDelta | None = None,
    usage_sink: UsageSink | None = None,
    bindings: KbRetrievalBindings | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """
    端到端 RAG：检索 → 拼 prompt → LLM 生成。

    ``model`` 由调用方 resolve（装配点语义，见 ``resolve_invoke_model``），
    直接用于生成；用量经 ``usage_sink`` 注入。
    ``retrieve_query`` 仅用于向量检索；``query`` 写入生成 prompt（可含「请根据附图回答」）。
    ``bindings`` 透传给 ``retrieve_hits``（embed/rerank 由 L1 装配注入）。
    ``media_reader`` 由 L1 注入，用于解析 ``media`` 附图。
    返回 (answer 文本, hits) 便于调用方展示引用来源。
    """
    search_q = (retrieve_query if retrieve_query is not None else query).strip()
    hits = await retrieve_hits(
        search_q,
        tenant_id=tenant_id,
        kb_ids=kb_ids,
        db=db,
        top_k=top_k,
        bindings=bindings,
    )
    prompt = build_rag_prompt(system_prompt=system_prompt, query=query, hits=hits)
    answer = await generate_rag_answer(
        model=model,
        prompt=prompt,
        media=media,
        media_reader=media_reader,
        temperature=temperature,
        on_delta=on_delta,
        usage_sink=usage_sink,
    )
    return answer, hits
