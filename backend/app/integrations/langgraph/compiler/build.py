"""将 graph_json 编译为 LangGraph StateGraph。"""

from __future__ import annotations

import operator
from dataclasses import replace
from typing import Annotated, Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.flow_runtime.constants import CanvasNodeType
from app.flow_runtime.nodes.registry import execute_node
from app.flow_runtime.step_record import build_flow_node_step
from app.flow_runtime.types import FlowGraph, RunContext
from app.integrations.langgraph.compiler.report import resolve_node_type
from app.integrations.langgraph.compiler.state import (
    gather_node_inputs,
    make_condition_router,
    make_relevance_grade_router,
    merge_outputs,
)
from app.integrations.langgraph.compiler.validate import validate_graph_for_compile
from app.integrations.langgraph.graph_analysis import (
    GRADE_BRANCH_HANDLES,
    build_incoming,
    build_outgoing,
    find_end_nodes,
    find_start_nodes,
    normalize_branch_handle,
    normalize_grade_handle,
)


def build_canvas_graph(graph_json: dict[str, Any]):
    """
    将 ``graph_json`` 编译为未 compile 的 ``StateGraph``。

    状态字段：``tenant_id``、``inputs``、``kb_ids``（供 KnowledgeSearch）、
    ``outputs``（reducer 合并）、``steps``（operator.add 累积审计）；
    ``resolve_model`` / ``usage_sink`` 为 L1 注入的画布 LLM 回调，随 ctx 透传。
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

    def _make_node_runner(node_id: str):
        """闭包：单画布节点 → ``execute_node``，写入 ``outputs[node_id]`` 与 ``steps``。"""

        async def run_node(state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
            """LangGraph 节点函数：聚合入边 → execute_node → 写入 outputs/steps。"""
            node = node_map[node_id]
            node_data = node.get("data") or {}
            if not isinstance(node_data, dict):
                node_data = {}
            ntype = resolve_node_type(node)
            ctx = replace(
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
                usage_sink=state.get("usage_sink"),
                kb_retrieval=state.get("kb_retrieval"),
                resolve_generative_image=state.get("resolve_generative_image"),
                resolve_generative_video=state.get("resolve_generative_video"),
                submit_generative_image=state.get("submit_generative_image"),
                submit_generative_video=state.get("submit_generative_video"),
            )
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

    from typing import TypedDict

    class _State(TypedDict, total=False):
        """LangGraph 画布状态；outputs/steps 使用 reducer 合并并行分支。"""

        tenant_id: str
        inputs: dict[str, Any]
        kb_ids: list[str]
        model_config_id: str | None
        system_prompt: str | None
        user_id: str | None
        permissions: list[str]
        is_superuser: bool
        agent_id: str | None
        agent_config: dict[str, Any]
        current_flow_id: str | None
        subflow_depth: int
        # L1 注入的画布 LLM 解析回调与用量记录器（随 ctx 透传，编译图单次内存执行）
        resolve_model: Any
        usage_sink: Any
        # L1 注入的 KB 检索绑定载体（随 ctx 透传，KnowledgeSearch 节点装配）
        kb_retrieval: Any
        # L1 注入的生图/生视频模型解析回调（随 ctx 透传，ImageGenerate/VideoGenerate 同步分支）
        resolve_generative_image: Any
        resolve_generative_video: Any
        # L1 注入的生图/生视频异步 job 提交回调（随 ctx 透传，ImageGenerate/VideoGenerate 异步分支）
        submit_generative_image: Any
        submit_generative_video: Any
        outputs: Annotated[dict[str, Any], merge_outputs]
        steps: Annotated[list[dict[str, Any]], operator.add]
        answer: Any

    g = StateGraph(_State)

    for nid in node_map:
        g.add_node(nid, _make_node_runner(nid))

    for start_id in find_start_nodes(fg):
        g.add_edge(START, start_id)

    for edge in fg.edges:
        src, tgt, sh, _th = edge.get("source"), edge.get("target"), edge.get("sourceHandle"), edge.get("targetHandle")
        if not src or not tgt:
            continue
        if src in condition_ids:
            continue
        g.add_edge(src, tgt)

    for cond_id in condition_ids:
        cond_node = node_map.get(cond_id, {})
        cond_type = resolve_node_type(cond_node)
        routes: dict[str, str] = {}
        if cond_type == CanvasNodeType.RELEVANCE_GRADE:
            for tgt, sh, _th in outgoing.get(cond_id, []):
                branch = normalize_grade_handle(sh)
                if branch in GRADE_BRANCH_HANDLES:
                    routes[branch] = tgt
            if routes:
                g.add_conditional_edges(
                    cond_id,
                    make_relevance_grade_router(cond_id),
                    routes,
                )
        else:
            for tgt, sh, _th in outgoing.get(cond_id, []):
                branch = normalize_branch_handle(sh)
                if branch in ("true", "false"):
                    routes[branch] = tgt
            if len(routes) >= 2:
                g.add_conditional_edges(cond_id, make_condition_router(cond_id), routes)

    end_ids = find_end_nodes(fg, resolve_node_type)
    for end_id in end_ids:
        if end_id not in condition_ids:
            g.add_edge(end_id, END)

    if not end_ids:
        g.add_edge(report.node_order[-1], END)

    return g
