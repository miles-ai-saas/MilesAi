"""内置流程画布模板 registry 与 GET /flows/templates。"""

import json

import pytest

from app.flow_runtime.templates.registry import (
    FLOW_TEMPLATE_REGISTRY,
    list_flow_templates,
    load_flow_template_graph,
)
from app.integrations.langgraph.compiler import validate_graph_for_compile


def test_registry_has_expected_ids():
    ids = {spec.id for spec in FLOW_TEMPLATE_REGISTRY}
    assert ids == {"blank", "rag", "simple_llm", "rag_with_grade"}


def test_blank_template_empty_graph():
    graph = load_flow_template_graph("blank")
    assert graph == {"nodes": [], "edges": []}


def test_rag_with_grade_template_compilable():
    graded = load_flow_template_graph("rag_with_grade")
    report = validate_graph_for_compile(graded)
    assert report.compilable, report.errors


@pytest.mark.parametrize("template_id", ["rag", "simple_llm"])
def test_non_blank_templates_compilable(template_id: str):
    graph = load_flow_template_graph(template_id)
    report = validate_graph_for_compile(graph)
    assert report.compilable, report.errors


def test_list_flow_templates_includes_graph_json():
    items = list_flow_templates()
    assert len(items) == len(FLOW_TEMPLATE_REGISTRY)
    rag = next(i for i in items if i["id"] == "rag")
    assert rag["default_name"] == "RAG 问答流程"
    assert len(rag["graph_json"]["nodes"]) >= 4


def test_insertable_only_excludes_blank_and_rag_with_grade():
    items = list_flow_templates(insertable_only=True)
    assert all(i["insertable"] for i in items)
    assert {"blank", "rag_with_grade"}.isdisjoint({i["id"] for i in items})


def test_rag_grade_file_for_marketplace():
    from tests.paths import BACKEND_ROOT

    graph = json.loads((BACKEND_ROOT / "app/flow_runtime/templates/rag_flow_with_grade.json").read_text(encoding="utf-8"))
    report = validate_graph_for_compile(graph)
    assert report.compilable
    assert "grade_1" in report.conditional_nodes
