"""编译报告 error_details 与 node_id。"""

from miles_ai.flow_runtime.compiler import validate_graph_for_compile


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


def test_edge_to_unknown_node_reports_structured_error_instead_of_raising():
    """回归：连线指向未声明的节点时必须返回结构化错误，而不是 KeyError 冒成 500。

    此前 ``topo_order`` / ``compute_execution_layers`` 会对未声明的 target 直接
    ``deps[child] -= 1``，于是保存流程时抛 ``KeyError: 'ghost'``。
    """
    graph = {
        "nodes": [{"id": "a", "type": "TextInput", "data": {}}],
        "edges": [{"source": "a", "target": "ghost"}],
    }

    report = validate_graph_for_compile(graph)

    assert not report.compilable
    assert any(e["code"] == "unknown_edge_endpoint" and e["node_id"] == "ghost" for e in report.error_details)


def test_edge_from_unknown_node_reports_structured_error():
    """同一缺陷的另一半：source 未声明时不得只报一个误导性的 no_entry。"""
    graph = {
        "nodes": [{"id": "a", "type": "TextOutput", "data": {}}],
        "edges": [{"source": "ghost", "target": "a"}],
    }

    report = validate_graph_for_compile(graph)

    assert not report.compilable
    assert any(e["code"] == "unknown_edge_endpoint" and e["node_id"] == "ghost" for e in report.error_details)


def test_unknown_edge_endpoint_is_reported_once_per_node():
    graph = {
        "nodes": [{"id": "a", "type": "TextInput", "data": {}}, {"id": "b", "type": "TextOutput", "data": {}}],
        "edges": [
            {"source": "a", "target": "ghost"},
            {"source": "b", "target": "ghost"},
        ],
    }

    report = validate_graph_for_compile(graph)

    hits = [e for e in report.error_details if e["code"] == "unknown_edge_endpoint"]
    assert len(hits) == 1
    assert hits[0]["node_id"] == "ghost"
