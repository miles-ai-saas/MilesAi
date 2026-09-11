"""
画布 ``graph_json`` 结构分析（环检测、并行层、条件边）。

供 ``integrations.langgraph.compiler`` 在编译前校验拓扑：
- ``has_cycle`` / ``topo_order``：可否 DAG 编译
- ``compute_execution_layers``：同层节点可并行（报告 ``parallel_groups``）
- ``normalize_branch_handle``：ConditionBranch 的 sourceHandle → true/false
- ``find_start_nodes`` / ``find_end_nodes``：接 START / END
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from miles_ai.flow_runtime.constants import TEXT_OUTPUT_NODE_TYPES
from miles_ai.flow_runtime.types import FlowGraph
from miles_ai.integrations.langgraph.constants import GRADE_BRANCH_HANDLES


def _edge_endpoints(edge: dict[str, Any]) -> tuple[str | None, str | None, str, str]:
    """统一 React Flow 边字段（source/target + Handle）。"""
    src = edge.get("source") or edge.get("source_id")
    tgt = edge.get("target") or edge.get("target_id")
    sh = edge.get("sourceHandle") or "output"
    th = edge.get("targetHandle") or "input"
    return src, tgt, sh, th


def build_outgoing(fg: FlowGraph) -> dict[str, list[tuple[str, str, str]]]:
    """source -> [(target, sourceHandle, targetHandle)]。"""
    outgoing: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for edge in fg.edges:
        src, tgt, sh, th = _edge_endpoints(edge)
        if src and tgt:
            outgoing[src].append((tgt, sh, th))
    return outgoing


def build_incoming(fg: FlowGraph) -> dict[str, list[tuple[str, str, str]]]:
    """target -> [(source, sourceHandle, targetHandle)]"""
    incoming: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for edge in fg.edges:
        src, tgt, sh, th = _edge_endpoints(edge)
        if src and tgt:
            incoming.setdefault(tgt, []).append((src, sh, th))
    return incoming


def topo_order(fg: FlowGraph) -> list[str]:
    """Kahn 拓扑排序；有环时退回节点声明顺序。"""
    node_ids = {n["id"] for n in fg.nodes}
    incoming = build_incoming(fg)
    deps = {nid: len(incoming.get(nid, [])) for nid in node_ids}
    queue = [nid for nid, d in deps.items() if d == 0]
    order: list[str] = []
    children: dict[str, list[str]] = defaultdict(list)
    for edge in fg.edges:
        src, tgt, _, _ = _edge_endpoints(edge)
        if src and tgt:
            children[src].append(tgt)
    while queue:
        nid = queue.pop(0)
        order.append(nid)
        for child in children.get(nid, []):
            deps[child] -= 1
            if deps[child] == 0:
                queue.append(child)
    return order if len(order) == len(node_ids) else [n["id"] for n in fg.nodes]


def has_cycle(fg: FlowGraph) -> bool:
    """是否存在有向环（不可编译 LangGraph）。"""
    order = topo_order(fg)
    return len(order) != len({n["id"] for n in fg.nodes})


def compute_execution_layers(fg: FlowGraph) -> list[list[str]]:
    """按依赖分批；同层节点可并行执行。"""
    if has_cycle(fg):
        return []

    incoming = build_incoming(fg)
    children: dict[str, list[str]] = defaultdict(list)
    for edge in fg.edges:
        src, tgt, _, _ = _edge_endpoints(edge)
        if src and tgt:
            children[src].append(tgt)

    node_ids = [n["id"] for n in fg.nodes]
    in_degree = {nid: len(incoming.get(nid, [])) for nid in node_ids}
    layers: list[list[str]] = []
    queue = [nid for nid in node_ids if in_degree[nid] == 0]

    visited = 0
    while queue:
        layers.append(list(queue))
        visited += len(queue)
        next_queue: list[str] = []
        for nid in queue:
            for child in children.get(nid, []):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    next_queue.append(child)
        queue = next_queue

    if visited != len(node_ids):
        return []
    return layers


def normalize_branch_handle(handle: str) -> str:
    """条件边 sourceHandle 归一化为 true/false。"""
    h = (handle or "output").strip().lower()
    if h in ("true", "yes", "1", "branch_true"):
        return "true"
    if h in ("false", "no", "0", "branch_false"):
        return "false"
    return h


def normalize_grade_handle(handle: str) -> str:
    """RelevanceGrade 条件边 sourceHandle → good / poor / none。"""
    h = (handle or "").strip().lower()
    if h in GRADE_BRANCH_HANDLES:
        return h
    return h


def find_start_nodes(fg: FlowGraph) -> list[str]:
    """无入边的节点（流程入口）。"""
    incoming = build_incoming(fg)
    return [n["id"] for n in fg.nodes if not incoming.get(n["id"])]


def find_end_nodes(fg: FlowGraph, resolve_type) -> list[str]:
    """无出边节点，或 TextOutput 类型节点。"""
    outgoing = build_outgoing(fg)
    ends = [n["id"] for n in fg.nodes if not outgoing.get(n["id"])]
    if ends:
        return ends
    return [n["id"] for n in fg.nodes if resolve_type(n) in TEXT_OUTPUT_NODE_TYPES]
