"""画布 graph_json → LangGraph 编译。"""

from app.ai_stack.langgraph.compiler import can_compile_flow_graph, validate_graph_for_compile
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


def test_rag_template_compilable():
    import json
    from pathlib import Path

    tpl_path = Path(__file__).resolve().parents[1] / "app/flow_runtime/templates/rag_flow.json"
    graph = json.loads(tpl_path.read_text())
    assert can_compile_flow_graph(graph)


def test_validate_rag_graph():
    report = validate_graph_for_compile(RAG_GRAPH)
    assert report.compilable
    assert report.engine == "langgraph"
    assert len(report.node_order) == 5


def test_unknown_node_not_compilable():
    bad = {
        "nodes": [{"id": "x", "type": "UnknownNode", "data": {}}],
        "edges": [],
    }
    report = validate_graph_for_compile(bad)
    assert not report.compilable
    assert report.errors
