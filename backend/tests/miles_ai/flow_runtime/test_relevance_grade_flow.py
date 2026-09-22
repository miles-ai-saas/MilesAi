"""RelevanceGrade / StaticResponse 画布编译与节点。"""

import json

import pytest

import miles_ai.flow_runtime.nodes.grade_nodes as grade_nodes_module
from miles_ai.flow_runtime.compiler import validate_graph_for_compile
from miles_ai.flow_runtime.nodes.grade_nodes import relevance_grade
from miles_ai.flow_runtime.types import RunContext
from miles_common.exceptions import BadRequestError
from tests.paths import MILES_AI


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
    path = MILES_AI / "flow_runtime/templates/rag_flow_with_grade.json"
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


@pytest.mark.asyncio
async def test_relevance_grade_llm_uses_resolve_model(monkeypatch):
    """LLM 评分：模型经 ctx.resolve_model 解析并传给 evaluate_relevance。"""
    sentinel_model = object()
    captured: dict[str, object] = {}

    async def fake_resolve(model_id: str) -> object:
        captured["model_id"] = model_id
        return sentinel_model

    async def fake_evaluate(hits, *, query, threshold, use_llm_grade, model):
        captured.update(
            hits=hits,
            query=query,
            threshold=threshold,
            use_llm_grade=use_llm_grade,
            model=model,
        )
        return {"relevance": "good", "hits": hits}

    monkeypatch.setattr(grade_nodes_module, "evaluate_relevance", fake_evaluate)

    ctx = RunContext(
        tenant_id="00000000-0000-0000-0000-000000000001",
        inputs={"query": "q"},
        resolve_model=fake_resolve,
    )
    hits = [{"content": "a", "score": 0.8}]
    out = await relevance_grade(
        {"relevance_threshold": 0.4, "use_llm_grade": True, "model_config_id": "m-1"},
        {"hits": hits},
        ctx,
    )
    assert captured["model_id"] == "m-1"
    assert captured["use_llm_grade"] is True
    assert captured["model"] is sentinel_model
    assert out == {"relevance": "good", "hits": hits}


@pytest.mark.asyncio
async def test_relevance_grade_llm_missing_resolve_model_raises():
    """LLM 评分但运行上下文缺 resolve_model：显式报错（对齐 llm_call）。"""
    ctx = RunContext(tenant_id="00000000-0000-0000-0000-000000000001", inputs={"query": "q"})
    with pytest.raises(BadRequestError):
        await relevance_grade(
            {"use_llm_grade": True, "model_config_id": "m-1"},
            {"hits": [{"content": "a", "score": 0.8}]},
            ctx,
        )
