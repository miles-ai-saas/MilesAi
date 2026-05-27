"""SubFlow 节点：嵌套调用同租户已发布流程。"""

from __future__ import annotations

from typing import Any

from app.common.exceptions import BadRequestError
from app.flow_runtime.constants import MAX_SUBFLOW_DEPTH
from app.flow_runtime.subflow.resolve import (
    build_child_context,
    pick_subflow_output,
    resolve_subflow_graph,
    summarize_child_steps,
)
from app.flow_runtime.types import RunContext
from app.infra.db import AsyncSessionLocal


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

    async with AsyncSessionLocal() as db:
        from uuid import UUID

        graph_json = await resolve_subflow_graph(
            db,
            node_data,
            UUID(ctx.tenant_id),
        )

    child_ctx = build_child_context(
        ctx,
        inputs,
        node_data,
        parent_flow_id=parent_flow_id,
        parent_node_id=parent_node_id,
        child_flow_id=sub_flow_id,
    )

    from app.flow_runtime.runtime_factory import get_flow_runtime

    runtime = get_flow_runtime()
    result = await runtime.run(graph_json, child_ctx)
    output = pick_subflow_output(result.output, node_data.get("output_key"))
    child_summary = summarize_child_steps(result.steps)

    return {
        "output": output,
        "child_flow_id": sub_flow_id,
        "child_steps": child_summary,
        "child_step_count": len(result.steps),
    }
