"""RelevanceGrade / StaticResponse 画布编译与节点。"""

import json
from pathlib import Path

import pytest

from app.flow_runtime.nodes.grade_nodes import relevance_grade
from app.flow_runtime.types import RunContext
from app.integrations.langgraph.compiler import validate_graph_for_compile


@pytest.mark.asyncio
async def test_relevance_grade_no_hits():
    ctx = RunContext(tenant_id="00000000-0000-0000-0000-000000000001", inputs={"query": "q"})
    out = await relevance_grade(
        {"relevance_threshold": 0.35},
        {"hits": []},
        ctx,
    )
    assert out["relevance"] == "none"
    assert out["hits"] == []


@pytest.mark.asyncio
async def test_relevance_grade_good_score():
    ctx = RunContext(tenant_id="00000000-0000-0000-0000-000000000001", inputs={"query": "q"})
    hits = [{"content": "a", "score": 0.8}]
    out = await relevance_grade(
        {"relevance_threshold": 0.35},
        {"hits": hits},
        ctx,
    )
    assert out["relevance"] == "good"
    assert out["hits"] == hits


def test_rag_with_grade_template_compilable():
    path = (
        Path(__file__).resolve().parents[1]
        / "app/flow_runtime/templates/rag_flow_with_grade.json"
    )
    graph = json.loads(path.read_text(encoding="utf-8"))
    report = validate_graph_for_compile(graph)
    assert report.compilable, report.errors
    assert "grade_1" in report.conditional_nodes


def test_grade_missing_branch_fails():
    graph = {
        "nodes": [
            {"id": "g", "type": "RelevanceGrade", "data": {}},
            {"id": "t", "type": "TextOutput", "data": {}},
        ],
        "edges": [
            {"source": "g", "target": "t", "sourceHandle": "good", "targetHandle": "input"},
        ],
    }
    report = validate_graph_for_compile(graph)
    assert not report.compilable
    assert any(e["code"] == "incomplete_grade_edges" for e in report.error_details)
