"""画布流程统一由 LangGraph 执行（L3）。

编译与并行/条件分支见 compiler.py；节点实现注册在 flow_runtime.nodes.registry。
"""

from __future__ import annotations

from app.integrations.langgraph.compiler import run_compiled_canvas, validate_graph_for_compile
from app.common.exceptions import BadRequestError
from app.flow_runtime.types import RunContext, RunResult


async def run_flow_graph(graph_json: dict, ctx: RunContext) -> RunResult:
    """执行 graph_json；不可编译时抛出 BadRequestError。"""
    report = validate_graph_for_compile(graph_json)
    if not report.compilable:
        detail = "; ".join(report.errors) or "流程图无法编译为 LangGraph"
        raise BadRequestError(detail)
    output, steps = await run_compiled_canvas(graph_json, ctx)
    return RunResult(output=output, steps=steps)
