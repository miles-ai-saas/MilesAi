"""KB 检索绑定载体（L3 中立，不依赖 tenant 域）。

供 L1 kb 域 ``tenant.kb.services.embeddings`` 构造、``vectorstores`` 检索函数
注入到 L2 ``rag.retrieve.multi_kb``；类型别名直接复用 multi_kb 的回调签名。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.rag.retrieve.multi_kb import (
    EmbedQueryAsync,
    EmbedQuerySync,
    ResolveRerankAsync,
    ResolveRerankSync,
)


@dataclass(frozen=True)
class KbRetrievalBindings:
    """KB 检索能力载体：embed/rerank 回调。

    sync 组供同步工具/脚本路径，async 组供 Agent RAG 与画布 KnowledgeSearch；
    由 L1 装配并注入，L3/L2 只调用回调、不感知租户细节。
    """

    embed_query_sync: EmbedQuerySync
    embed_query: EmbedQueryAsync
    resolve_rerank_sync: ResolveRerankSync | None = None
    resolve_rerank: ResolveRerankAsync | None = None
