"""
RAG 检索增强生成（线性路径，无 LangGraph）。

适用场景
--------
- 简单「多 KB 问答」API 或脚本：retrieve → 拼 prompt → ``ainvoke_chat``。
- 复杂 Agent / 流程画布走 ``rag.graph`` / ``flow_runtime``，不经过本模块。

依赖
----
- 检索：``rag.retrieve.multi_kb.search_multi_kb_async``。
- 上下文：``generate.context.build_rag_user_prompt``。

有附图但未传 ``media_reader`` 时显式 ``BadRequestError``，避免静默丢图。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_ai.integrations.chat.multimodal import build_invoke_messages_with_media
from miles_ai.integrations.langchain.chat_models import OnDelta, ainvoke_chat
from miles_ai.integrations.litellm.usage_sink import UsageSink
from miles_ai.rag.generate.context import build_rag_user_prompt
from miles_ai.rag.load import load_kbs_for_tenant
from miles_ai.rag.retrieve.bindings import KbRetrievalBindings
from miles_ai.rag.retrieve.multi_kb import search_multi_kb_async
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
