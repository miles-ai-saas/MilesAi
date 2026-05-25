"""
画布流程 LangGraph 执行入口（L3）。

流程
----
``graph_json`` → ``validate_graph_for_compile`` → ``run_compiled_canvas``
→ 各层并行/条件边 → ``execute_node`` → ``NODE_REGISTRY`` handler。

RAG 节点不经过 Agent LangGraph RAG 图（``graphs/rag_qa``），仅在画布内 ``retrieve_hits``。
"""

from __future__ import annotations

from app.integrations.langgraph.compiler import run_compiled_canvas, validate_graph_for_compile
from app.common.exceptions import BadRequestError
from app.flow_runtime.types import RunContext, RunResult


async def run_flow_graph(graph_json: dict, ctx: RunContext) -> RunResult:
    """校验并编译画布 → LangGraph 执行 → RunResult(output, steps)。"""
    report = validate_graph_for_compile(graph_json)
    if not report.compilable:
        detail = "; ".join(report.errors) or "流程图无法编译为 LangGraph"
        raise BadRequestError(detail)
    output, steps = await run_compiled_canvas(graph_json, ctx)
    return RunResult(output=output, steps=steps)
