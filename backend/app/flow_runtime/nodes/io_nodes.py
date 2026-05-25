"""画布 I/O 节点：从 RunContext.inputs 读入、向上游汇聚写出。

TextInput 为流程入口；TextOutput 取首个非空上游值作为 run 终点（FlowService.run 的 output）。
"""

from typing import Any

from app.flow_runtime.types import RunContext


async def text_input(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> str:
    """从 RunContext.inputs 或节点默认值读取入口文本。"""
    key = node_data.get("input_key") or "query"
    if key in ctx.inputs:
        return str(ctx.inputs[key])
    return str(node_data.get("input_value") or ctx.inputs.get("query", ""))


async def text_output(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> str:
    """取上游第一个非空输出作为流程终点。"""
    for v in inputs.values():
        if v is not None:
            return str(v)
    return ""
