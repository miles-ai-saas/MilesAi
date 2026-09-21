"""并行与条件分支编译分析。"""

from miles_ai.flow_runtime.types import FlowGraph
from miles_ai.integrations.langgraph.compiler import validate_graph_for_compile
from miles_ai.integrations.langgraph.graph_analysis import compute_execution_layers

PARALLEL_FANOUT = {
    "nodes": [
        {"id": "in", "type": "TextInput", "data": {}},
        {"id": "a", "type": "PromptTemplate", "data": {"template": "{{query}}"}},
        {"id": "b", "type": "PromptTemplate", "data": {"template": "B {{query}}"}},
        {"id": "join", "type": "ParallelJoin", "data": {"merge_strategy": "concat_text"}},
        {"id": "out", "type": "TextOutput", "data": {}},
    ],
    "edges": [
        {"source": "in", "target": "a", "sourceHandle": "output", "targetHandle": "query"},
        {"source": "in", "target": "b", "sourceHandle": "output", "targetHandle": "query"},
        {"source": "a", "target": "join", "sourceHandle": "output", "targetHandle": "a"},
        {"source": "b", "target": "join", "sourceHandle": "output", "targetHandle": "b"},
        {"source": "join", "target": "out", "sourceHandle": "output", "targetHandle": "input"},
    ],
}

CONDITION_GRAPH = {
    "nodes": [
        {"id": "in", "type": "TextInput", "data": {}},
        {"id": "search", "type": "KnowledgeSearch", "data": {"top_k": 3}},
        {"id": "cond", "type": "ConditionBranch", "data": {"mode": "has_hits"}},
        {"id": "yes", "type": "PromptTemplate", "data": {"template": "Y {{input}}"}},
        {"id": "no", "type": "PromptTemplate", "data": {"template": "N"}},
        {"id": "out_y", "type": "TextOutput", "data": {}},
        {"id": "out_n", "type": "TextOutput", "data": {}},
    ],
    "edges": [
        {"source": "in", "target": "search", "sourceHandle": "output", "targetHandle": "query"},
        {"source": "search", "target": "cond", "sourceHandle": "output", "targetHandle": "hits"},
        {"source": "cond", "target": "yes", "sourceHandle": "true", "targetHandle": "input"},
        {"source": "cond", "target": "no", "sourceHandle": "false", "targetHandle": "input"},
        {"source": "yes", "target": "out_y", "sourceHandle": "output", "targetHandle": "input"},
        {"source": "no", "target": "out_n", "sourceHandle": "output", "targetHandle": "input"},
    ],
}


def test_parallel_layers():
    layers = compute_execution_layers(FlowGraph.from_dict(PARALLEL_FANOUT))
    assert ["in"] == layers[0]
    assert set(layers[1]) == {"a", "b"}


def test_parallel_compile_report():
    report = validate_graph_for_compile(PARALLEL_FANOUT)
    assert report.compilable
    assert len(report.parallel_groups) >= 1


def test_condition_compile_report():
    report = validate_graph_for_compile(CONDITION_GRAPH)
    assert report.compilable
    assert "cond" in report.conditional_nodes


def test_condition_missing_handles_fails():
    bad = {
        "nodes": [
            {"id": "c", "type": "ConditionBranch", "data": {}},
            {"id": "t", "type": "TextOutput", "data": {}},
        ],
        "edges": [
            {"source": "c", "target": "t", "sourceHandle": "true", "targetHandle": "input"},
        ],
    }
    report = validate_graph_for_compile(bad)
    assert not report.compilable
