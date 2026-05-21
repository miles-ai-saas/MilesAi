"""内置流程执行器（Langflow 未安装或调试时使用）。"""

from typing import Any

from app.langflow.nodes.registry import execute_node
from app.langflow.types import FlowGraph, RunContext, RunResult


def _build_adjacency(graph: FlowGraph) -> dict[str, list[tuple[str, str, str]]]:
    """target -> [(source, sourceHandle, targetHandle)]"""
    incoming: dict[str, list[tuple[str, str, str]]] = {}
    for edge in graph.edges:
        src = edge.get("source") or edge.get("source_id")
        tgt = edge.get("target") or edge.get("target_id")
        if not src or not tgt:
            continue
        incoming.setdefault(tgt, []).append(
            (src, edge.get("sourceHandle") or "output", edge.get("targetHandle") or "input")
        )
    return incoming


def _topo_order(graph: FlowGraph) -> list[str]:
    node_ids = {n["id"] for n in graph.nodes}
    incoming = _build_adjacency(graph)
    deps = {nid: len(incoming.get(nid, [])) for nid in node_ids}
    queue = [nid for nid, d in deps.items() if d == 0]
    order: list[str] = []
    children: dict[str, list[str]] = {}
    for edge in graph.edges:
        src = edge.get("source") or edge.get("source_id")
        tgt = edge.get("target") or edge.get("target_id")
        if src and tgt:
            children.setdefault(src, []).append(tgt)
    while queue:
        nid = queue.pop(0)
        order.append(nid)
        for child in children.get(nid, []):
            deps[child] -= 1
            if deps[child] == 0:
                queue.append(child)
    return order if len(order) == len(node_ids) else [n["id"] for n in graph.nodes]


class BuiltinFlowRuntime:
    async def run(self, graph: dict, ctx: RunContext) -> RunResult:
        fg = FlowGraph.from_dict(graph)
        node_map = {n["id"]: n for n in fg.nodes}
        incoming = _build_adjacency(fg)
        outputs: dict[str, Any] = {}
        steps: list[dict[str, Any]] = []

        for node_id in _topo_order(fg):
            node = node_map.get(node_id)
            if not node:
                continue
            node_data = node.get("data") or {}
            if not isinstance(node_data, dict):
                node_data = {}
            node_type = (
                node_data.get("type")
                or node.get("type")
                or node.get("node_type")
            )
            if node_type in ("genericNode", "customNode") and node_data.get("type"):
                node_type = node_data.get("type")

            node_inputs: dict[str, Any] = {}
            for src, _sh, th in incoming.get(node_id, []):
                if src in outputs:
                    node_inputs[th] = outputs[src]
                    node_inputs.setdefault("input", outputs[src])
                    if th == "query":
                        node_inputs["query"] = outputs[src]

            result = await execute_node(str(node_type), node_data, node_inputs, ctx)
            outputs[node_id] = result
            steps.append({"node_id": node_id, "type": node_type, "output_preview": str(result)[:200]})

        final = None
        for node in fg.nodes:
            ntype = node.get("type") or (node.get("data") or {}).get("type")
            if ntype in ("TextOutput", "ChatOutput"):
                final = outputs.get(node["id"])
        if final is None and outputs:
            final = list(outputs.values())[-1]

        return RunResult(output=final, steps=steps)
