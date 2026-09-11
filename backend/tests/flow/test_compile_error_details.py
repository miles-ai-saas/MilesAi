"""编译报告 error_details 与 node_id。"""

from miles_ai.integrations.langgraph.compiler import validate_graph_for_compile


def test_unknown_node_error_detail_has_node_id():
    bad = {
        "nodes": [{"id": "n1", "type": "UnknownNode", "data": {}}],
        "edges": [],
    }
    report = validate_graph_for_compile(bad)
    assert not report.compilable
    assert len(report.error_details) >= 1
    assert report.error_details[0]["node_id"] == "n1"
    assert report.error_details[0]["code"] == "unknown_node_type"
    assert "[n1]" in report.errors[0]


def test_platform_tool_missing_slug():
    graph = {
        "nodes": [
            {"id": "t1", "type": "PlatformTool", "data": {"label": "工具"}},
            {"id": "out", "type": "TextOutput", "data": {}},
        ],
        "edges": [
            {"source": "t1", "target": "out", "sourceHandle": "output", "targetHandle": "input"},
        ],
    }
    report = validate_graph_for_compile(graph)
    assert not report.compilable
    codes = [e["code"] for e in report.error_details]
    assert "missing_tool_slug" in codes
    assert any(e["node_id"] == "t1" for e in report.error_details)
