"""SubFlow 节点：嵌套调用同租户已发布流程。

解析 ``sub_flow_id`` 对应 graph_json，通过 ``run_subflow`` 执行子图；
``MAX_SUBFLOW_DEPTH`` 限制嵌套层数，与 LoopNode 共用同一深度计数。
"""

from __future__ import annotations

from typing import Any

from miles_common.exceptions import BadRequestError
from miles_ai.flow_runtime.constants import MAX_SUBFLOW_DEPTH
from miles_ai.flow_runtime.subflow.resolve import (
    build_child_context,
    pick_subflow_output,
    summarize_child_steps,
)
from miles_ai.flow_runtime.types import RunContext


async def sub_flow(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> dict[str, Any]:
    """执行嵌套子流程 run。"""
    if ctx.subflow_depth >= MAX_SUBFLOW_DEPTH:
        raise BadRequestError(f"子流程嵌套深度超过 {MAX_SUBFLOW_DEPTH} 层")

    sub_flow_id = str(node_data.get("sub_flow_id") or "").strip()
    if not sub_flow_id:
        raise BadRequestError("SubFlow 节点须配置 sub_flow_id")

    parent_flow_id = ctx.current_flow_id or ctx.parent_flow_id
    parent_node_id = ctx.executing_node_id or ""

    if ctx.load_subflow_graph is None:
        raise BadRequestError("运行上下文未提供子流程图加载回调")
    graph_json = await ctx.load_subflow_graph(node_data, ctx.tenant_id)

    child_ctx = build_child_context(
        ctx,
        inputs,
        node_data,
        parent_flow_id=parent_flow_id,
        parent_node_id=parent_node_id,
        child_flow_id=sub_flow_id,
    )

    run_subflow = ctx.run_subflow
    if run_subflow is None:
        from miles_ai.flow_runtime.runtime_factory import get_flow_runtime  # pragma: no cover

        run_subflow = get_flow_runtime().run

    result = await run_subflow(graph_json, child_ctx)
    output = pick_subflow_output(result.output, node_data.get("output_key"))
    child_summary = summarize_child_steps(result.steps)

    return {
        "output": output,
        "child_flow_id": sub_flow_id,
        "child_steps": child_summary,
        "child_step_count": len(result.steps),
    }
