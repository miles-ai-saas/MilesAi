"""LoopNode：循环执行 SubFlow，支持固定次数或条件退出。

每次迭代调用 ``run_subflow`` 执行子流程；``carry_output=True`` 时将上轮输出合并为下轮输入。
``condition_field`` 指定子流程输出中的退出字段，值为 falsy 时提前结束循环。
"""

from __future__ import annotations

from typing import Any

from miles_ai.flow_runtime.constants import MAX_SUBFLOW_DEPTH
from miles_ai.flow_runtime.subflow.resolve import (
    build_child_context,
    pick_subflow_output,
    summarize_child_steps,
)
from miles_ai.flow_runtime.types import RunContext
from miles_common.exceptions import BadRequestError


async def loop_node(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> dict[str, Any]:
    """循环执行子流程。

    node_data:
        sub_flow_id: 每次迭代执行的子流程 ID
        max_iterations: 最大迭代次数（默认 10）
        condition_field: 可选，子流程输出中作为退出条件的字段名；值为 falsy 时提前退出
        carry_output: 是否将上次输出作为下次输入（默认 True）
    """
    if ctx.subflow_depth >= MAX_SUBFLOW_DEPTH:
        raise BadRequestError(f"循环节点嵌套深度超过 {MAX_SUBFLOW_DEPTH} 层")

    sub_flow_id = str(node_data.get("sub_flow_id") or "").strip()
    if not sub_flow_id:
        raise BadRequestError("LoopNode 须配置 sub_flow_id")

    max_iterations = int(node_data.get("max_iterations") or 10)
    if max_iterations < 1:
        max_iterations = 1
    if max_iterations > 100:
        max_iterations = 100

    condition_field = str(node_data.get("condition_field") or "").strip() or None
    carry_output = node_data.get("carry_output", True)

    parent_flow_id = ctx.current_flow_id or ctx.parent_flow_id
    parent_node_id = ctx.executing_node_id or ""

    if ctx.load_subflow_graph is None:
        raise BadRequestError("运行上下文未提供子流程图加载回调")
    graph_json = await ctx.load_subflow_graph(node_data, ctx.tenant_id)

    all_steps: list[dict] = []
    current_inputs = dict(inputs)
    last_output: Any = None

    run_subflow = ctx.run_subflow
    if run_subflow is None:
        from miles_ai.flow_runtime.runtime_factory import get_flow_runtime

        run_subflow = get_flow_runtime().run  # pragma: no cover — 兜底路径（正常由 graph_runner 注入）

    for iteration in range(1, max_iterations + 1):
        child_ctx = build_child_context(
            ctx,
            current_inputs,
            node_data,
            parent_flow_id=parent_flow_id,
            parent_node_id=parent_node_id,
            child_flow_id=sub_flow_id,
        )

        result = await run_subflow(graph_json, child_ctx)
        output = pick_subflow_output(result.output, node_data.get("output_key"))

        all_steps.append(
            {
                "iteration": iteration,
                "steps": summarize_child_steps(result.steps),
                "output": output,
            }
        )

        # 条件退出检查
        if condition_field and isinstance(output, dict):
            value = output.get(condition_field)
            if not value:
                break

        # 将输出作为下一轮输入
        if carry_output:
            if isinstance(output, dict):
                current_inputs = {**current_inputs, **output}
            else:
                current_inputs["previous_output"] = output

        last_output = output

    return {
        "output": last_output,
        "child_flow_id": sub_flow_id,
        "iterations": len(all_steps),
        "max_iterations": max_iterations,
        "all_steps": all_steps,
        "early_exit": condition_field and len(all_steps) < max_iterations,
    }
