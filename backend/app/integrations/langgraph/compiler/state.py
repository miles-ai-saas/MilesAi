"""LangGraph 状态 reducer、入边聚合与条件路由。"""

from typing import Any

from app.flow_runtime.constants import TEXT_OUTPUT_NODE_TYPES
from app.flow_runtime.types import FlowGraph
from app.integrations.langgraph.constants import RELEVANCE_NONE
from app.integrations.langgraph.graph_analysis import GRADE_BRANCH_HANDLES, normalize_branch_handle, normalize_grade_handle
from app.integrations.langgraph.compiler.report import resolve_node_type


def merge_outputs(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """LangGraph State 中 outputs 字段的 reducer。"""
    return {**left, **right}


def gather_node_inputs(
    node_id: str,
    incoming: dict[str, list[tuple[str, str, str]]],
    outputs: dict[str, Any],
) -> dict[str, Any]:
    """
    按入边 ``targetHandle`` 聚合上游 ``outputs[node_id]``。

    同时设置 ``input`` 为首个入边值；``rag_flow.json`` 典型：search→prompt 的 handle 为 ``hits``。
    媒体节点可经 ``media`` handle 接收上游附件列表。
    """
    node_inputs: dict[str, Any] = {}
    for src, _sh, th in incoming.get(node_id, []):
        if src not in outputs:
            continue
        raw = outputs[src]
        if isinstance(raw, dict) and "output" in raw:
            val = raw["output"]
        else:
            val = raw
        node_inputs[th] = val
        node_inputs.setdefault("input", val)
        if th == "query":
            node_inputs["query"] = val
        if th == "hits" and val is not None:
            node_inputs["hits"] = val
        if isinstance(raw, dict) and raw.get("hits") is not None:
            node_inputs.setdefault("hits", raw["hits"])
        if th in ("true", "false") and isinstance(raw, dict):
            node_inputs[th] = raw
        if th in GRADE_BRANCH_HANDLES and isinstance(raw, dict):
            node_inputs[th] = raw
        if th == "media" and val is not None:
            node_inputs.setdefault("media", val)
    return node_inputs


def resolve_final_output(fg: FlowGraph, outputs: dict[str, Any]) -> Any:
    """优先 TextOutput 节点值，否则取最后节点输出。"""
    for node in fg.nodes:
        ntype = resolve_node_type(node)
        if ntype in TEXT_OUTPUT_NODE_TYPES:
            val = outputs.get(node["id"])
            if isinstance(val, dict) and "output" in val:
                return val["output"]
            if val is not None:
                return val
    if outputs:
        last = list(outputs.values())[-1]
        if isinstance(last, dict) and "output" in last:
            return last["output"]
        return last
    return None


def make_condition_router(condition_node_id: str):
    """
    条件节点路由：读取 ``ConditionBranch`` 输出的 ``branch`` 字段（``true``/``false``）。

    画布须从该节点拉出两条边，``sourceHandle`` 分别为 ``true`` 与 ``false``，例如：
    ``search_1`` → ``cond_1`` → (true) ``llm_ok`` / (false) ``fallback_prompt``。
    """

    def router(state: dict[str, Any]) -> str:
        raw = (state.get("outputs") or {}).get(condition_node_id, {})
        if isinstance(raw, dict):
            return normalize_branch_handle(str(raw.get("branch", "false")))
        return "false"

    return router


def make_relevance_grade_router(grade_node_id: str):
    """RelevanceGrade 路由：读取 ``relevance`` 字段（good/poor/none）。"""

    def router(state: dict[str, Any]) -> str:
        raw = (state.get("outputs") or {}).get(grade_node_id, {})
        if isinstance(raw, dict):
            rel = str(raw.get("relevance", RELEVANCE_NONE)).strip().lower()
            if rel in GRADE_BRANCH_HANDLES:
                return rel
        return RELEVANCE_NONE

    return router
