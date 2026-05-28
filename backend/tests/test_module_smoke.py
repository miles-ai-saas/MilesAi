"""拆分后模块 import smoke：KB 服务与 LangGraph 编译器。"""

from app.integrations.langgraph.compiler import (
    FlowCompileReport,
    build_canvas_graph,
    validate_graph_for_compile,
)
from app.tenant.kb.services.kb import KnowledgeBaseService


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
