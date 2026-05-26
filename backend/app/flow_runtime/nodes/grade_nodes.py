"""画布相关性评分节点（对齐 Agent ``rag_qa.grade_documents``）。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.flow_runtime.types import RunContext
from app.infra.db import AsyncSessionLocal
from app.integrations.langgraph.grading import evaluate_relevance
from app.models.model import ModelConfig
from app.tenant.models.services.model_resolve import resolve_model_for_invoke


async def relevance_grade(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> dict[str, Any]:
    """根据检索 hits 输出 good / poor / none，供三路条件边路由。"""
    hits = inputs.get("hits")
    if hits is None and isinstance(inputs.get("input"), list):
        hits = inputs.get("input")
    if not isinstance(hits, list):
        hits = []

    threshold = float(node_data.get("relevance_threshold", 0.35))
    use_llm = bool(node_data.get("use_llm_grade", False))
    query = str(inputs.get("query") or ctx.inputs.get("query", ""))

    model: ModelConfig | None = None
    model_id = node_data.get("model_config_id") or ctx.model_config_id
    if use_llm and model_id:
        async with AsyncSessionLocal() as db:
            model = (
                await db.execute(
                    select(ModelConfig).where(
                        ModelConfig.id == model_id,
                        ModelConfig.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()
            if model:
                model = await resolve_model_for_invoke(db, model, UUID(str(ctx.tenant_id)))

    result = await evaluate_relevance(
        hits,
        query=query,
        threshold=threshold,
        use_llm_grade=use_llm and model is not None,
        model=model,
    )
    return result
