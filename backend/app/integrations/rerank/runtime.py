"""Rerank 运行时入口。"""

from __future__ import annotations

from app.integrations.rerank.model_meta import ensure_rerank_model_type
from app.integrations.rerank.registry import rerank_documents_for_model
from app.integrations.rerank.types import RerankHit
from app.models.model import ModelConfig


def rerank_documents(
    model: ModelConfig,
    *,
    query: str,
    documents: list[str],
    top_n: int | None = None,
) -> list[RerankHit]:
    ensure_rerank_model_type(model)
    return rerank_documents_for_model(
        model,
        query=query,
        documents=documents,
        top_n=top_n,
    )
