"""画布相关性评分节点（对齐 Agent ``rag_qa.grade_documents``）。

输出 ``relevance`` 为 good / poor / none，compiler 映射为三路条件边 handle。
``use_llm_grade=True`` 时委托 ``integrations.langgraph.grading.llm_grade_relevance``。

模型解析由运行入口注入的 ``RunContext.resolve_model`` 回调完成（同 ``llm_nodes``，
见 ``tenant.flows.services.run_context.make_flow_model_resolver``）；节点不再自行查询。
LLM 评分所需模型缺失或回调缺失时抛 ``BadRequestError``，便于调试与兜底。
"""

from __future__ import annotations

from typing import Any

from app.common.exceptions import BadRequestError
from app.flow_runtime.types import RunContext
from app.integrations.langgraph.grading import evaluate_relevance


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

    model = None
    model_id = node_data.get("model_config_id") or ctx.model_config_id
    if use_llm and model_id:
        if ctx.resolve_model is None:
            raise BadRequestError("运行上下文未提供模型解析回调")
        model = await ctx.resolve_model(str(model_id))

    result = await evaluate_relevance(
        hits,
        query=query,
        threshold=threshold,
        use_llm_grade=use_llm and model is not None,
        model=model,
    )
    return result
