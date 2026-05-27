"""
React Flow ``graph_json`` → LangGraph ``StateGraph`` 编译器（画布流程 L3）。

与 Agent RAG 图的区别
--------------------
- **本模块**：``build_canvas_graph`` / ``run_compiled_canvas``，状态 ``outputs`` 按 node_id 合并
- **rag_qa**：固定 retrieve→grade→generate 图，带 checkpointer 多轮（见 ``graphs/rag_qa``）

编译策略
--------
1. ``validate_graph_for_compile``：无环、入口、条件边 true/false、节点类型在 registry 内
2. ``build_canvas_graph``：每个画布 id 一个 LangGraph node；普通边 ``add_edge``；
   ``ConditionBranch`` 用 ``add_conditional_edges``（读 ``branch`` 字段）
3. 并行：同 ``execution_layers`` 一层多节点由 LangGraph 按无依赖边自然扇出（非显式 Send API）

RAG 相关 handle（``_gather_node_inputs``）
---------------------------------------
- ``query`` → KnowledgeSearch / PromptTemplate
- ``hits`` → 上游 KnowledgeSearch 输出列表
- ``prompt`` → LLMCall
- ``media`` → OcrExtract / AudioTranscribe（含 attachment_id 的媒体列表）
- ``input`` → ComplianceCheck 等文本扫描节点的默认入边

P2 节点（Loop / 合规 / 媒体）
-----------------------------
- ``LoopNode`` / ``SubFlow``：编译期校验 ``sub_flow_id``；运行时 ``ctx.run_subflow`` 递归
- ``ComplianceCheck``：输出 ``passed`` / ``hits``，可接 ConditionBranch
- ``OcrExtract`` / ``AudioTranscribe``：附件 → 纯文本，常作 LLMCall 前置

``SUPPORTED_CANVAS_NODE_TYPES`` 与 ``flow_runtime.nodes.registry`` 键名必须一致。

文档
----
- 内置 RAG 模板边示例：``flow_runtime/templates/README.md``
- 用户文档：``docs/guides/flows.md``
"""

from __future__ import annotations

import operator
from typing import Annotated, Any

from dataclasses import replace

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.flow_runtime.constants import CanvasNodeType, TEXT_OUTPUT_NODE_TYPES
from app.integrations.langgraph.constants import RELEVANCE_NONE
from app.integrations.langgraph.graph_analysis import (
    GRADE_BRANCH_HANDLES,
    build_incoming,
    build_outgoing,
    compute_execution_layers,
    find_end_nodes,
    find_start_nodes,
    has_cycle,
    normalize_branch_handle,
    normalize_grade_handle,
)
from app.integrations.langgraph.graph_analysis import topo_order
from app.flow_runtime.nodes.registry import NODE_REGISTRY, execute_node
from app.flow_runtime.step_record import build_flow_node_step
from app.flow_runtime.types import FlowGraph, RunContext

# 与前端调色板、flow_runtime.nodes.registry 保持一致
SUPPORTED_CANVAS_NODE_TYPES = frozenset(NODE_REGISTRY.keys())


def resolve_node_type(node: dict[str, Any]) -> str:
    """从 React Flow 节点 JSON 解析 registry 键名。"""
    node_data = node.get("data") or {}
    if not isinstance(node_data, dict):
        node_data = {}
    node_type = node_data.get("type") or node.get("type") or node.get("node_type") or ""
    if node_type in ("genericNode", "customNode") and node_data.get("type"):
        node_type = node_data.get("type")
    return str(node_type)


def _compile_error(
    code: str,
    message: str,
    *,
    node_id: str | None = None,
) -> dict[str, Any]:
    """结构化编译错误；``errors`` 字符串列表与之同步生成。"""
    return {"code": code, "message": message, "node_id": node_id}


def _error_to_str(err: dict[str, Any]) -> str:
    """将结构化编译错误格式化为 ``[node_id] message`` 便于展示。"""
    nid = err.get("node_id")
    msg = str(err.get("message") or "")
    if nid:
        return f"[{nid}] {msg}"
    return msg


class FlowCompileReport:
    """画布编译诊断结果（工作台「编译预览」/ ``FlowService`` 校验用）。"""

    __slots__ = (
        "compilable",
        "engine",
        "node_order",
        "node_types",
        "execution_layers",
        "parallel_groups",
        "conditional_nodes",
        "errors",
        "error_details",
    )

    def __init__(
        self,
        *,
        compilable: bool,
        engine: str,
        node_order: list[str],
        node_types: list[str],
        execution_layers: list[list[str]],
        parallel_groups: list[list[str]],
        conditional_nodes: list[str],
        errors: list[str],
        error_details: list[dict[str, Any]] | None = None,
    ):
        """compilable=False 时 engine 为 ``builtin``，仅用于诊断不可执行。"""
        self.compilable = compilable
        self.engine = engine
        self.node_order = node_order
        self.node_types = node_types
        self.execution_layers = execution_layers
        self.parallel_groups = parallel_groups
        self.conditional_nodes = conditional_nodes
        self.errors = errors
        self.error_details = error_details or []

    def to_dict(self) -> dict[str, Any]:
        """序列化为 API / 编译预览 JSON。"""
        return {
            "compilable": self.compilable,
            "engine": self.engine,
            "node_order": self.node_order,
            "node_types": self.node_types,
            "execution_layers": self.execution_layers,
            "parallel_groups": self.parallel_groups,
            "conditional_nodes": self.conditional_nodes,
            "errors": self.errors,
            "error_details": self.error_details,
        }


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
            # LoopNode 与 SubFlow 共用 sub_flow_id；迭代次数在运行时 clamp 1–100
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


def _merge_outputs(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """LangGraph State 中 outputs 字段的 reducer。"""
    return {**left, **right}


def _gather_node_inputs(
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


def _resolve_final_output(fg: FlowGraph, outputs: dict[str, Any]) -> Any:
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


def _make_condition_router(condition_node_id: str):
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


def _make_relevance_grade_router(grade_node_id: str):
    """RelevanceGrade 路由：读取 ``relevance`` 字段（good/poor/none）。"""

    def router(state: dict[str, Any]) -> str:
        raw = (state.get("outputs") or {}).get(grade_node_id, {})
        if isinstance(raw, dict):
            rel = str(raw.get("relevance", RELEVANCE_NONE)).strip().lower()
            if rel in GRADE_BRANCH_HANDLES:
                return rel
        return RELEVANCE_NONE

    return router


def build_canvas_graph(graph_json: dict[str, Any]):
    """
    将 ``graph_json`` 编译为未 compile 的 ``StateGraph``。

    状态字段：``tenant_id``、``inputs``、``kb_ids``（供 KnowledgeSearch）、
    ``outputs``（reducer 合并）、``steps``（operator.add 累积审计）。
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
            )
            node_inputs = _gather_node_inputs(node_id, incoming, state.get("outputs") or {})
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
        outputs: Annotated[dict[str, Any], _merge_outputs]
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
                    _make_relevance_grade_router(cond_id),
                    routes,
                )
        else:
            for tgt, sh, _th in outgoing.get(cond_id, []):
                branch = normalize_branch_handle(sh)
                if branch in ("true", "false"):
                    routes[branch] = tgt
            if len(routes) >= 2:
                g.add_conditional_edges(cond_id, _make_condition_router(cond_id), routes)

    end_ids = find_end_nodes(fg, resolve_node_type)
    for end_id in end_ids:
        if end_id not in condition_ids:
            g.add_edge(end_id, END)

    if not end_ids:
        g.add_edge(report.node_order[-1], END)

    return g


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
    output = _resolve_final_output(fg, outputs)
    steps = final.get("steps") or []
    return output, steps
