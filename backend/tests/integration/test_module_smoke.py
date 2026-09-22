"""拆分后模块 import smoke：KB 服务与 LangGraph 编译器。"""

from miles_ai.flow_runtime.compiler import (
    FlowCompileReport,
    build_canvas_graph,
    validate_graph_for_compile,
)
from miles_portal.tenant.kb.services.kb import KnowledgeBaseService


def test_kb_service_and_compiler_imports():
    assert KnowledgeBaseService.__name__ == "KnowledgeBaseService"
    assert FlowCompileReport.__name__ == "FlowCompileReport"
    assert callable(build_canvas_graph)
    assert callable(validate_graph_for_compile)


def test_minimal_flow_graph_compiles():
    graph = {
        "nodes": [
            {
                "id": "out_1",
                "type": "TextOutput",
                "data": {"type": "TextOutput", "label": "输出"},
                "position": {"x": 0, "y": 0},
            }
        ],
        "edges": [],
    }
    report = validate_graph_for_compile(graph)
    assert isinstance(report, FlowCompileReport)
    assert report.compilable is True
    assert report.engine == "langgraph"


def test_minimal_flow_graph_builds_state_graph():
    graph = {
        "nodes": [
            {
                "id": "in_1",
                "type": "TextInput",
                "data": {"type": "TextInput", "label": "输入", "input_key": "query"},
                "position": {"x": 0, "y": 0},
            },
            {
                "id": "out_1",
                "type": "TextOutput",
                "data": {"type": "TextOutput", "label": "输出"},
                "position": {"x": 200, "y": 0},
            },
        ],
        "edges": [
            {
                "id": "e1",
                "source": "in_1",
                "target": "out_1",
                "sourceHandle": "output",
                "targetHandle": "input",
            }
        ],
    }
    report = validate_graph_for_compile(graph)
    assert report.compilable is True
    state_graph = build_canvas_graph(graph)
    compiled = state_graph.compile()
    assert compiled is not None
