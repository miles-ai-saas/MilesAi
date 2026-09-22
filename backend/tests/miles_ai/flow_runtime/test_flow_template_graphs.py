"""内置流程模板 graph_json 可编译性。"""

import pytest

from miles_ai.flow_runtime.compiler import validate_graph_for_compile
from miles_ai.flow_runtime.templates.registry import FLOW_TEMPLATE_REGISTRY, load_flow_template_graph


@pytest.mark.parametrize(
    "template_id",
    [spec.id for spec in FLOW_TEMPLATE_REGISTRY if spec.graph_file],
)
def test_builtin_flow_template_compilable(template_id: str) -> None:
    graph = load_flow_template_graph(template_id)
    report = validate_graph_for_compile(graph)
    assert report.compilable, f"{template_id}: {report.errors}"
