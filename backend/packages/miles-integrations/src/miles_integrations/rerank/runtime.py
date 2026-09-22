"""
Rerank 运行时入口。

``retriever.apply_rerank_to_hits`` 在解析好 ``ModelConfig`` 后调用 ``rerank_documents``，
再经 ``registry`` 分发至 DashScope / OpenAI 兼容等 Provider。
"""

from __future__ import annotations

from miles_core.models.model import ModelConfig
from miles_integrations.rerank.model_meta import ensure_rerank_model_type
from miles_integrations.rerank.registry import rerank_documents_for_model
from miles_integrations.rerank.types import RerankHit


def rerank_documents(
    model: ModelConfig,
    *,
    query: str,
    documents: list[str],
    top_n: int | None = None,
) -> list[RerankHit]:
    """校验模型类型后调用 registry 重排。"""
    ensure_rerank_model_type(model)
    return rerank_documents_for_model(
        model,
        query=query,
        documents=documents,
        top_n=top_n,
    )
