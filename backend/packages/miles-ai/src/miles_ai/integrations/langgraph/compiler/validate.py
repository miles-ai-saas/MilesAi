"""画布图编译前校验。"""

from typing import Any

from miles_ai.flow_runtime.constants import CanvasNodeType
from miles_ai.flow_runtime.types import FlowGraph
from miles_ai.integrations.langgraph.graph_analysis import (
    GRADE_BRANCH_HANDLES,
    build_outgoing,
    compute_execution_layers,
    find_start_nodes,
    has_cycle,
    normalize_branch_handle,
    normalize_grade_handle,
    topo_order,
)
from miles_ai.integrations.langgraph.compiler.report import (
    FlowCompileReport,
    SUPPORTED_CANVAS_NODE_TYPES,
    _compile_error,
    _error_to_str,
    resolve_node_type,
)


def validate_graph_for_compile(graph: dict[str, Any]) -> FlowCompileReport:
    """
    分析画布是否可编译为 LangGraph。

    ``execution_layers``：同层可并行；``parallel_groups`` 为层内节点数 >1 的子集。
    ``engine``：可编译时为 ``langgraph``，否则 ``builtin``（仅诊断，不执行）。
    """
    fg = FlowGraph.from_dict(graph)
    error_details: list[dict[str, Any]] = []

    def add_error(code: str, message: str, *, node_id: str | None = None) -> None:
        error_details.append(_compile_error(code, message, node_id=node_id))

    if not fg.nodes:
        add_error("empty_graph", "流程图为空")
        return FlowCompileReport(
            compilable=False,
            engine="builtin",
            node_order=[],
            node_types=[],
            execution_layers=[],
            parallel_groups=[],
            conditional_nodes=[],
            errors=[_error_to_str(e) for e in error_details],
            error_details=error_details,
        )

    if has_cycle(fg):
        add_error("cycle", "流程图存在环，无法编译")

    node_map = {n["id"]: n for n in fg.nodes}
    order = topo_order(fg) if not has_cycle(fg) else []
    layers = compute_execution_layers(fg)
    parallel_groups = [layer for layer in layers if len(layer) > 1]
    conditional_nodes: list[str] = []
    outgoing = build_outgoing(fg)

    types: list[str] = []
    for nid in order:
        node = node_map.get(nid)
        if not node:
            continue
        ntype = resolve_node_type(node)
        types.append(ntype)
        if ntype not in SUPPORTED_CANVAS_NODE_TYPES:
            add_error(
                "unknown_node_type",
                f"节点类型 {ntype!r} 暂不支持 LangGraph 编译",
                node_id=nid,
            )
        if ntype == "PlatformTool":
            node_data = node.get("data") or {}
            if not isinstance(node_data, dict):
                node_data = {}
            slug = str(node_data.get("tool_slug") or node_data.get("slug") or "").strip()
            if not slug:
                add_error(
                    "missing_tool_slug",
                    "平台工具节点须配置 tool_slug",
                    node_id=nid,
                )
        if ntype == CanvasNodeType.SUB_FLOW:
            node_data = node.get("data") or {}
            if not isinstance(node_data, dict):
                node_data = {}
            if not str(node_data.get("sub_flow_id") or "").strip():
                add_error(
                    "missing_sub_flow_id",
                    "SubFlow 节点须配置 sub_flow_id",
                    node_id=nid,
                )
        if ntype == CanvasNodeType.LOOP:
            node_data = node.get("data") or {}
            if not isinstance(node_data, dict):
                node_data = {}
            if not str(node_data.get("sub_flow_id") or "").strip():
                add_error(
                    "missing_sub_flow_id",
                    "LoopNode 须配置 sub_flow_id",
                    node_id=nid,
                )
            iterations = int(node_data.get("max_iterations") or 10)
            if iterations < 1 or iterations > 100:
                add_error(
                    "invalid_max_iterations",
                    f"LoopNode max_iterations 须在 1–100 之间，当前: {iterations}",
                    node_id=nid,
                )
        if ntype == CanvasNodeType.CONDITION:
            conditional_nodes.append(nid)
            handles = {normalize_branch_handle(sh) for _, sh, _ in outgoing.get(nid, [])}
            if "true" not in handles or "false" not in handles:
                add_error(
                    "incomplete_condition_edges",
                    "条件节点须同时连出 sourceHandle=true 与 false 两条边",
                    node_id=nid,
                )
        if ntype == CanvasNodeType.RELEVANCE_GRADE:
            conditional_nodes.append(nid)
            handles = {normalize_grade_handle(sh) for _, sh, _ in outgoing.get(nid, [])}
            missing = GRADE_BRANCH_HANDLES - handles
            if missing:
                add_error(
                    "incomplete_grade_edges",
                    f"相关性评分节点须连出 good/poor/none 分支，缺少: {', '.join(sorted(missing))}",
                    node_id=nid,
                )

    if not find_start_nodes(fg):
        add_error("no_entry", "缺少入口节点（无入边的节点）")

    errors = [_error_to_str(e) for e in error_details]
    compilable = not error_details
    return FlowCompileReport(
        compilable=compilable,
        engine="langgraph" if compilable else "builtin",
        node_order=order,
        node_types=types,
        execution_layers=layers,
        parallel_groups=parallel_groups,
        conditional_nodes=conditional_nodes,
        errors=errors,
        error_details=error_details,
    )


def can_compile_flow_graph(graph: dict[str, Any]) -> bool:
    """快捷判断 compilable。"""
    return validate_graph_for_compile(graph).compilable
