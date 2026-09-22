"""``build_canvas_graph`` 的结构性特征化测试。

该函数负责把 ``graph_json`` 接成 LangGraph 拓扑。此前只有「整条流程跑通」的
端到端覆盖，接线本身（起点/终点边、直连边与条件分支的分流、句柄归一化与过滤）
没有任何断言。拆分前先按结构锁死。
"""

from __future__ import annotations

import json

import pytest

from miles_ai.flow_runtime.compiler.build import (
    _run_context_from_state,
    build_canvas_graph,
)
from tests.paths import MILES_AI

RAG_GRAPH = {
    "nodes": [
        {"id": "input_1", "type": "TextInput", "data": {"input_key": "query"}},
        {"id": "search_1", "type": "KnowledgeSearch", "data": {"top_k": 5}},
        {"id": "prompt_1", "type": "PromptTemplate", "data": {"template": "Q: {{用户提问}}"}},
        {"id": "llm_1", "type": "LLMCall", "data": {"temperature": 0.7}},
        {"id": "output_1", "type": "TextOutput", "data": {}},
    ],
    "edges": [
        {"source": "input_1", "target": "search_1", "sourceHandle": "output", "targetHandle": "query"},
        {"source": "input_1", "target": "prompt_1", "sourceHandle": "output", "targetHandle": "query"},
        {"source": "search_1", "target": "prompt_1", "sourceHandle": "output", "targetHandle": "hits"},
        {"source": "prompt_1", "target": "llm_1", "sourceHandle": "output", "targetHandle": "prompt"},
        {"source": "llm_1", "target": "output_1", "sourceHandle": "output", "targetHandle": "input"},
    ],
}

TWO_START_GRAPH = {
    "nodes": [
        {"id": "a", "type": "TextInput", "data": {"input_key": "q1"}},
        {"id": "b", "type": "TextInput", "data": {"input_key": "q2"}},
        {"id": "out", "type": "TextOutput", "data": {}},
    ],
    "edges": [
        {"source": "a", "target": "out", "sourceHandle": "output", "targetHandle": "input"},
        {"source": "b", "target": "out", "sourceHandle": "output", "targetHandle": "input"},
    ],
}

GRADE_EXTRA_HANDLE = {
    "nodes": [
        {"id": "in", "type": "TextInput", "data": {"input_key": "query"}},
        {"id": "g", "type": "RelevanceGrade", "data": {}},
        {"id": "ok", "type": "TextOutput", "data": {}},
        {"id": "fb", "type": "StaticResponse", "data": {}},
    ],
    "edges": [
        {"source": "in", "target": "g", "sourceHandle": "output", "targetHandle": "hits"},
        # 大小写不同 → 归一化后仍应命中 good
        {"source": "g", "target": "ok", "sourceHandle": "GOOD", "targetHandle": "input"},
        {"source": "g", "target": "ok", "sourceHandle": "poor", "targetHandle": "input"},
        {"source": "g", "target": "fb", "sourceHandle": "none", "targetHandle": "input"},
        # 未知句柄 → 不应出现在分支表里
        {"source": "g", "target": "fb", "sourceHandle": "weird", "targetHandle": "input"},
    ],
}


def _grade_template() -> dict:
    path = MILES_AI / "flow_runtime/templates/rag_flow_with_grade.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _edges(graph) -> set[tuple[str, str]]:  # noqa: ANN001
    return {(str(src), str(tgt)) for src, tgt in graph.edges}


# --- 直连边与起终点 -----------------------------------------------------------


def test_nodes_and_straight_edges_are_wired():
    g = build_canvas_graph(RAG_GRAPH)

    assert set(g.nodes) == {"input_1", "search_1", "prompt_1", "llm_1", "output_1"}
    assert _edges(g) == {
        ("__start__", "input_1"),
        ("input_1", "search_1"),
        ("input_1", "prompt_1"),
        ("search_1", "prompt_1"),
        ("prompt_1", "llm_1"),
        ("llm_1", "output_1"),
        ("output_1", "__end__"),
    }
    assert g.branches == {}


def test_every_start_node_gets_edge_from_start():
    g = build_canvas_graph(TWO_START_GRAPH)

    assert {("__start__", "a"), ("__start__", "b")} <= _edges(g)
    assert g.branches == {}


# --- 条件节点：出边转分支 -----------------------------------------------------


def test_grade_outgoing_edges_become_branches_not_straight_edges():
    g = build_canvas_graph(_grade_template())

    assert g.branches["grade_1"]["router"].ends == {
        "good": "prompt_1",
        "poor": "prompt_1",
        "none": "fallback_1",
    }
    # 条件节点的出边不进直连边，也不接 END
    assert not any(src == "grade_1" for src, _ in _edges(g))
    assert ("grade_1", "__end__") not in _edges(g)


def test_grade_handles_are_normalized_and_unknown_ones_filtered():
    g = build_canvas_graph(GRADE_EXTRA_HANDLE)

    assert g.branches["g"]["router"].ends == {"good": "ok", "poor": "ok", "none": "fb"}
    assert not any(src == "g" for src, _ in _edges(g))


# --- 状态 → 执行上下文 --------------------------------------------------------

_CALLBACK_STATE_KEYS = (
    "resolve_model",
    "usage_sink_factory",
    "kb_retrieval",
    "resolve_generative_image",
    "resolve_generative_video",
    "submit_generative_image",
    "submit_generative_video",
    "invoke_platform_tool",
    "resolve_prompt_template",
    "load_scan_words",
    "load_subflow_graph",
    "media_reader",
    "generate_image_sync",
    "generate_video_sync",
)


def test_all_callback_state_keys_are_carried_over():
    """状态里的 L1 回调必须逐个透传——漏一个该能力就在画布内静默失效。"""
    markers = {key: object() for key in _CALLBACK_STATE_KEYS}

    ctx = _run_context_from_state({"tenant_id": "t", **markers}, "n")

    dropped = [key for key, marker in markers.items() if getattr(ctx, key) is not marker]
    assert dropped == []


def test_callbacks_default_to_none_when_absent():
    ctx = _run_context_from_state({"tenant_id": "t"}, "n")

    assert [key for key in _CALLBACK_STATE_KEYS if getattr(ctx, key) is not None] == []


def test_derived_fields_are_normalized_and_copied():
    agent_config = {"a": 1}
    media = [{"m": 1}]
    state = {
        "tenant_id": "t-1",
        "inputs": {"q": "x"},
        "kb_ids": ["kb"],
        "permissions": ["p1"],
        "is_superuser": 1,
        "agent_config": agent_config,
        "media": media,
        "subflow_depth": "2",
        "current_flow_id": "f-1",
        "agent_id": "a-1",
        "model_config_id": "m-1",
        "system_prompt": "sp",
        "user_id": "u-1",
    }

    ctx = _run_context_from_state(state, "node-9")

    assert ctx.executing_node_id == "node-9"  # 当前节点由参数指定
    assert (ctx.tenant_id, ctx.current_flow_id, ctx.agent_id) == ("t-1", "f-1", "a-1")
    assert (ctx.model_config_id, ctx.system_prompt, ctx.user_id) == ("m-1", "sp", "u-1")
    assert ctx.permissions == frozenset({"p1"})
    assert ctx.is_superuser is True
    assert ctx.subflow_depth == 2
    # 可变容器须拷贝，避免节点执行期间改到 state
    assert ctx.agent_config is not agent_config
    assert ctx.media is not media


def test_missing_state_fields_fall_back_to_defaults():
    ctx = _run_context_from_state({"tenant_id": "t"}, "n")

    assert ctx.inputs == {}
    assert ctx.kb_ids == []
    assert ctx.permissions == frozenset()
    assert ctx.is_superuser is False
    assert ctx.subflow_depth == 0
    assert ctx.agent_config == {}
    assert ctx.media == []
    assert ctx.model_config_id is None
    assert ctx.current_flow_id is None


# --- 不可编译 ---------------------------------------------------------------


def test_uncompilable_graph_raises_with_joined_errors():
    graph = {"nodes": [{"id": "x", "type": "UnknownNode", "data": {}}], "edges": []}

    with pytest.raises(ValueError) as excinfo:
        build_canvas_graph(graph)

    assert "[x]" in str(excinfo.value)
    assert "暂不支持" in str(excinfo.value)


def test_empty_graph_never_reaches_end_wiring():
    """空图由校验拦下，故 build 里无需「没有汇点就兜到最后一个节点」的兜底。

    该兜底已删：DAG 必有汇点，而空图 / 全是出边的图都过不了 ``validate_graph_for_compile``
    （「流程图为空」/ 环检测），走到 ``find_end_nodes`` 时 ``end_ids`` 必然非空。
    """
    with pytest.raises(ValueError, match="流程图为空"):
        build_canvas_graph({"nodes": [], "edges": []})
