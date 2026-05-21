from typing import Any

from app.langflow.types import RunContext


async def text_input(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> str:
    key = node_data.get("input_key") or "query"
    if key in ctx.inputs:
        return str(ctx.inputs[key])
    return str(node_data.get("input_value") or ctx.inputs.get("query", ""))


async def text_output(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> str:
    for v in inputs.values():
        if v is not None:
            return str(v)
    return ""
