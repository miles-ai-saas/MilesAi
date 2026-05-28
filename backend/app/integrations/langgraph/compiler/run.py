"""编译后画布图执行入口。"""

from typing import Any

from app.flow_runtime.types import FlowGraph, RunContext
from app.integrations.langgraph.compiler.build import build_canvas_graph
from app.integrations.langgraph.compiler.state import resolve_final_output
from app.integrations.langgraph.compiler.validate import validate_graph_for_compile


async def run_compiled_canvas(
    graph_json: dict[str, Any],
    ctx: RunContext,
) -> tuple[Any, list[dict[str, Any]]]:
    """
    执行编译后的画布图，返回 ``(output, steps)``。

    ``output`` 优先 ``TextOutput`` 节点；``ctx.kb_ids`` 传入 state 供 KnowledgeSearch。
    **不使用** RAG checkpointer（单次 run，无 ``thread_id`` 恢复）。
    """
    fg = FlowGraph.from_dict(graph_json)
    report = validate_graph_for_compile(graph_json)
    compiled = build_canvas_graph(graph_json).compile()
    initial: dict[str, Any] = {
        "tenant_id": ctx.tenant_id,
        "inputs": dict(ctx.inputs),
        "kb_ids": list(ctx.kb_ids),
        "model_config_id": ctx.model_config_id,
        "system_prompt": ctx.system_prompt,
        "user_id": ctx.user_id,
        "permissions": list(ctx.permissions),
        "is_superuser": ctx.is_superuser,
        "agent_id": ctx.agent_id,
        "agent_config": dict(ctx.agent_config),
        "current_flow_id": ctx.current_flow_id,
        "subflow_depth": ctx.subflow_depth,
        "media": list(ctx.media),
        "outputs": {},
        "steps": [
            {
                "type": "graph_start",
                "engine": "langgraph",
                "graph": "canvas",
                "parallel_groups": report.parallel_groups,
                "conditional_nodes": report.conditional_nodes,
            }
        ],
    }
    final = await compiled.ainvoke(initial, {})
    outputs = final.get("outputs") or {}
    output = resolve_final_output(fg, outputs)
    steps = final.get("steps") or []
    return output, steps
