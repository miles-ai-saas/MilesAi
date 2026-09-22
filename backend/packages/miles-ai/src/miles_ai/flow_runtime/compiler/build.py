"""将 graph_json 编译为 LangGraph StateGraph。"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from miles_ai.flow_runtime.compiler.report import resolve_node_type
from miles_ai.flow_runtime.compiler.state import (
    CanvasGraphState,
    gather_node_inputs,
    make_relevance_grade_router,
)
from miles_ai.flow_runtime.compiler.validate import validate_graph_for_compile
from miles_ai.flow_runtime.constants import CanvasNodeType
from miles_ai.flow_runtime.graph_analysis import (
    GRADE_BRANCH_HANDLES,
    build_incoming,
    build_outgoing,
    find_end_nodes,
    find_start_nodes,
    normalize_grade_handle,
)
from miles_ai.flow_runtime.nodes.registry import execute_node
from miles_ai.flow_runtime.step_record import build_flow_node_step
from miles_ai.flow_runtime.types import FlowGraph, RunContext


def _run_context_from_state(state: dict[str, Any], node_id: str) -> RunContext:
    """画布状态 → 节点执行上下文；``executing_node_id`` 为当前节点。

    状态里携带的 L1 回调（``resolve_model`` / ``usage_sink_factory`` / 各
    ``resolve_*`` / ``submit_*``）逐个透传，漏一个该能力就在画布内静默失效。
    """
    return replace(
        RunContext(
            tenant_id=state["tenant_id"],
            inputs=state.get("inputs") or {},
            kb_ids=state.get("kb_ids") or [],
            model_config_id=state.get("model_config_id"),
            system_prompt=state.get("system_prompt"),
            user_id=state.get("user_id"),
            permissions=frozenset(state.get("permissions") or []),
            is_superuser=bool(state.get("is_superuser")),
            agent_id=state.get("agent_id"),
            agent_config=dict(state.get("agent_config") or {}),
            media=list(state.get("media") or []),
            current_flow_id=state.get("current_flow_id"),
            subflow_depth=int(state.get("subflow_depth") or 0),
        ),
        executing_node_id=node_id,
        resolve_model=state.get("resolve_model"),
        usage_sink_factory=state.get("usage_sink_factory"),
        kb_retrieval=state.get("kb_retrieval"),
        resolve_generative_image=state.get("resolve_generative_image"),
        resolve_generative_video=state.get("resolve_generative_video"),
        submit_generative_image=state.get("submit_generative_image"),
        submit_generative_video=state.get("submit_generative_video"),
        invoke_platform_tool=state.get("invoke_platform_tool"),
        resolve_prompt_template=state.get("resolve_prompt_template"),
        load_scan_words=state.get("load_scan_words"),
        load_subflow_graph=state.get("load_subflow_graph"),
        media_reader=state.get("media_reader"),
        generate_image_sync=state.get("generate_image_sync"),
        generate_video_sync=state.get("generate_video_sync"),
    )


def _make_node_runner(node_id: str, node_map: dict[str, Any], incoming: dict[str, Any]):
    """构造单个画布节点的 LangGraph 执行函数（闭包固定 node_id 与图结构）。"""

    async def run_node(state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        """LangGraph 节点函数：聚合入边 → execute_node → 写入 outputs/steps。"""
        node = node_map[node_id]
        node_data = node.get("data") or {}
        if not isinstance(node_data, dict):
            node_data = {}
        ntype = resolve_node_type(node)
        ctx = _run_context_from_state(state, node_id)
        node_inputs = gather_node_inputs(node_id, incoming, state.get("outputs") or {})
        result = await execute_node(ntype, node_data, node_inputs, ctx)
        return {
            "outputs": {node_id: result},
            "steps": [
                build_flow_node_step(
                    node_id=node_id,
                    node_type=ntype,
                    result=result,
                )
            ],
        }

    return run_node


def _add_conditional_edges(g, cond_id: str, node_map: dict[str, Any], outgoing: dict[str, Any]) -> None:
    """条件节点的出边以分支表注册，而不是直连边。

    RelevanceGrade 的句柄归一化为 good/poor/none，未知句柄被丢弃，因此分支表就是
    「实际可走的分支」。

    这里只处理 RelevanceGrade：Condition 节点虽有 true/false 分支，但
    ``validate_graph_for_compile`` 判定其「暂不支持 LangGraph 编译」，构造
    ``StateGraph`` 之前就已抛错，故无需在此处理（原先的 true/false 接线与
    ``make_condition_router`` 因此不可达，已删）。若将来放开 Condition 编译，
    需在此补 ``normalize_branch_handle`` 的分支表与对应 router。
    """
    cond_type = resolve_node_type(node_map.get(cond_id, {}))
    if cond_type != CanvasNodeType.RELEVANCE_GRADE:
        return
    routes: dict[str, str] = {}
    for tgt, sh, _th in outgoing.get(cond_id, []):
        branch = normalize_grade_handle(sh)
        if branch in GRADE_BRANCH_HANDLES:
            routes[branch] = tgt
    if routes:
        g.add_conditional_edges(cond_id, make_relevance_grade_router(cond_id), routes)


def build_canvas_graph(graph_json: dict[str, Any]):
    """
    将 ``graph_json`` 编译为未 compile 的 ``StateGraph``。

    状态字段：``tenant_id``、``inputs``、``kb_ids``（供 KnowledgeSearch）、
    ``outputs``（reducer 合并）、``steps``（operator.add 累积审计）；
    ``resolve_model`` / ``usage_sink_factory`` 为 L1 注入的画布 LLM 回调，随 ctx 透传。
    调用方需 ``.compile()`` 后 ``ainvoke``（见 ``run_compiled_canvas``）。
    """
    report = validate_graph_for_compile(graph_json)
    if not report.compilable:
        raise ValueError("; ".join(report.errors) or "流程图不可编译")

    fg = FlowGraph.from_dict(graph_json)
    node_map = {n["id"]: n for n in fg.nodes}
    incoming = build_incoming(fg)
    outgoing = build_outgoing(fg)
    condition_ids = {nid for nid in report.conditional_nodes}

    g = StateGraph(CanvasGraphState)

    for nid in node_map:
        g.add_node(nid, _make_node_runner(nid, node_map, incoming))

    for start_id in find_start_nodes(fg):
        g.add_edge(START, start_id)

    for edge in fg.edges:
        src, tgt = edge.get("source"), edge.get("target")
        if not src or not tgt or src in condition_ids:
            continue
        g.add_edge(src, tgt)

    for cond_id in condition_ids:
        _add_conditional_edges(g, cond_id, node_map, outgoing)

    end_ids = find_end_nodes(fg, resolve_node_type)
    for end_id in end_ids:
        if end_id not in condition_ids:
            g.add_edge(end_id, END)

    return g
