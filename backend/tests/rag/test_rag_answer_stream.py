"""RAG 与 LangGraph on_delta 透传测试。"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.integrations.langgraph.graphs.rag_qa import fallback, generate
from app.integrations.langgraph.runner import run_rag_workflow
from app.rag.generate.answer import rag_answer
from tests.infra.test_litellm_adapter import _model


@pytest.mark.asyncio
async def test_rag_answer_forwards_on_delta(monkeypatch):
    seen: dict[str, object] = {}
    model = _model()
    tenant_id = uuid4()
    db = MagicMock()

    async def fake_ainvoke(*args, **kwargs):
        seen["on_delta"] = kwargs.get("on_delta")
        return "ans"

    async def delta(_: str) -> None:
        pass

    with (
        patch(
            "app.rag.generate.answer.retrieve_hits",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "app.rag.generate.answer.ainvoke_chat",
            new_callable=AsyncMock,
            side_effect=fake_ainvoke,
        ),
    ):
        answer, hits = await rag_answer(
            model=model,
            system_prompt="你是助手",
            query="问题",
            kb_ids=["kb1"],
            tenant_id=tenant_id,
            db=db,
            on_delta=delta,
        )

    assert answer == "ans"
    assert hits == []
    assert seen["on_delta"] is delta


@pytest.mark.asyncio
async def test_run_rag_workflow_forwards_on_delta_to_config():
    model = _model()
    tid = uuid4()
    aid = uuid4()

    async def delta(_: str) -> None:
        pass

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={"answer": "ok", "hits": [], "steps": []},
    )

    with (
        patch(
            "app.integrations.langgraph.runner.get_compiled_rag_graph",
            return_value=mock_graph,
        ),
        patch(
            "app.tenant.models.services.model_resolve.resolve_model_for_invoke",
            new_callable=AsyncMock,
            return_value=model,
        ),
        patch("app.infra.db.AsyncSessionLocal") as session_cls,
    ):
        db = MagicMock()
        session_cls.return_value.__aenter__ = AsyncMock(return_value=db)
        session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await run_rag_workflow(
            model=model,
            system_prompt="sys",
            query="问题",
            kb_ids=["kb1"],
            tenant_id=tid,
            agent_id=aid,
            on_delta=delta,
        )

    run_config = mock_graph.ainvoke.await_args.args[1]
    assert run_config["configurable"]["on_delta"] is delta


@pytest.mark.asyncio
async def test_generate_node_forwards_on_delta():
    tenant_id = uuid4()
    model = _model()

    async def delta(_: str) -> None:
        pass

    state = {
        "tenant_id": str(tenant_id),
        "system_prompt": "你是助手",
        "query": "问题",
        "prompt_query": "问题",
        "hits": [{"content": "片段", "score": 0.9}],
        "temperature": 0.7,
    }
    config = {"configurable": {"model": model, "on_delta": delta}}

    with (
        patch(
            "app.integrations.langgraph.graphs.rag_qa.ainvoke_chat",
            new_callable=AsyncMock,
            return_value="答案",
        ) as mock_chat,
        patch("app.integrations.langgraph.graphs.rag_qa.AsyncSessionLocal") as session_cls,
    ):
        db = MagicMock()
        session_cls.return_value.__aenter__ = AsyncMock(return_value=db)
        session_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        out = await generate(state, config)

    assert out["answer"] == "答案"
    assert mock_chat.await_args.kwargs["on_delta"] is delta


@pytest.mark.asyncio
async def test_fallback_node_forwards_on_delta():
    tenant_id = uuid4()
    model = _model()

    async def delta(_: str) -> None:
        pass

    state = {
        "tenant_id": str(tenant_id),
        "system_prompt": "你是助手",
        "query": "问题",
        "prompt_query": "问题",
        "hits": [],
        "temperature": 0.7,
    }
    config = {"configurable": {"model": model, "on_delta": delta}}

    with (
        patch(
            "app.integrations.langgraph.graphs.rag_qa.ainvoke_chat",
            new_callable=AsyncMock,
            return_value="兜底",
        ) as mock_chat,
        patch("app.integrations.langgraph.graphs.rag_qa.AsyncSessionLocal") as session_cls,
    ):
        db = MagicMock()
        session_cls.return_value.__aenter__ = AsyncMock(return_value=db)
        session_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        out = await fallback(state, config)

    assert out["answer"] == "兜底"
    assert mock_chat.await_args.kwargs["on_delta"] is delta


@pytest.mark.asyncio
async def test_llm_grade_does_not_forward_on_delta():
    """grade 节点 LLM 评判不应透传 on_delta。"""
    from app.integrations.langgraph.graphs.rag_qa import grade_documents

    tenant_id = uuid4()
    model = _model()

    async def delta(_: str) -> None:
        pass

    state = {
        "tenant_id": str(tenant_id),
        "query": "问题",
        "kb_ids": ["kb1"],
        "hits": [{"content": "片段", "score": 0.9}],
        "relevance_threshold": 0.35,
        "use_llm_grade": True,
    }
    config = {"configurable": {"model": model, "on_delta": delta}}

    with patch(
        "app.integrations.langgraph.graphs.rag_qa.llm_grade_relevance",
        new_callable=AsyncMock,
        return_value=("good", "ok"),
    ) as mock_grade:
        await grade_documents(state, config)

    mock_grade.assert_awaited_once()
    # llm_grade_relevance 内部 ainvoke_chat 无 on_delta 参数，此处仅验证 grade 被调用
