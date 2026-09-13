"""RAG 生成阶段多模态（检索仍文本 query）。"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from miles_ai.integrations.chat.multimodal import build_invoke_messages_with_media
from miles_ai.integrations.langgraph.graphs.rag_qa import _prompt_user_query, fallback, generate
from miles_ai.integrations.langgraph.runner import run_rag_workflow
from miles_ai.rag.generate.answer import rag_answer
from miles_common.exceptions import BadRequestError
from miles_common.schemas.media import MediaRefIn


def test_prompt_user_query_prefers_prompt_query():
    state = {"query": "检索用", "prompt_query": "生成用"}
    assert _prompt_user_query(state) == "生成用"


@pytest.mark.asyncio
async def test_build_invoke_messages_with_media():
    class FakeReader:
        async def read_image_bytes(self, attachment_id):
            from miles_core.models.media.reader import AttachmentBytes

            return AttachmentBytes(data=b"\x89PNG\r\n\x1a\n", mime="image/png")

    att_id = uuid4()
    msgs = await build_invoke_messages_with_media(
        FakeReader(),
        prompt_text="参考：...\n\n用户问题：看图",
        media=[MediaRefIn(attachment_id=att_id)],
    )
    assert isinstance(msgs[0]["content"], list)


@pytest.mark.asyncio
async def test_generate_node_with_media():
    tenant_id = uuid4()
    model = MagicMock()
    state = {
        "tenant_id": str(tenant_id),
        "system_prompt": "你是助手",
        "query": "检索词",
        "prompt_query": "描述图片",
        "hits": [{"content": "片段", "score": 0.9}],
        "temperature": 0.7,
        "media": [{"attachment_id": str(uuid4()), "detail": "auto"}],
    }
    config = {"configurable": {"model": model, "media_reader": MagicMock()}}

    with (
        patch(
            "miles_ai.integrations.langgraph.graphs.rag_qa.build_invoke_messages_with_media",
            new_callable=AsyncMock,
            return_value=[{"role": "user", "content": [{"type": "text", "text": "x"}]}],
        ) as mock_build,
        patch(
            "miles_ai.integrations.langgraph.graphs.rag_qa.ainvoke_chat",
            new_callable=AsyncMock,
            return_value="答案",
        ),
    ):
        out = await generate(state, config)

    assert out["answer"] == "答案"
    mock_build.assert_awaited_once()
    assert mock_build.await_args.args[0] is config["configurable"]["media_reader"]


@pytest.mark.asyncio
async def test_run_rag_workflow_passes_media_in_initial():
    model = MagicMock()
    att_id = uuid4()
    tid = uuid4()
    aid = uuid4()

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={"answer": "ok", "hits": [], "steps": []},
    )
    reader = object()

    with patch(
        "miles_ai.integrations.langgraph.runner.get_compiled_rag_graph",
        return_value=mock_graph,
    ):
        await run_rag_workflow(
            model=model,
            system_prompt="sys",
            query="检索",
            prompt_query="生成问题",
            kb_ids=["kb1"],
            tenant_id=tid,
            agent_id=aid,
            media=[MediaRefIn(attachment_id=att_id)],
            media_reader=reader,
        )

    initial = mock_graph.ainvoke.await_args.args[0]
    assert initial["query"] == "检索"
    assert initial["prompt_query"] == "生成问题"
    assert len(initial["media"]) == 1
    run_config = mock_graph.ainvoke.await_args.args[1]
    assert run_config["configurable"]["media_reader"] is reader


def _media_state() -> dict:
    return {
        "system_prompt": "你是助手",
        "query": "检索词",
        "prompt_query": "描述图片",
        "hits": [{"content": "片段", "score": 0.9}],
        "temperature": 0.7,
        "media": [{"attachment_id": str(uuid4()), "detail": "auto"}],
    }


@pytest.mark.asyncio
async def test_generate_node_with_media_without_reader_raises():
    """有附图但未装配 media_reader ⇒ 显式报错（不再静默丢图）。"""
    config = {"configurable": {"model": MagicMock()}}
    with pytest.raises(BadRequestError, match="media_reader"):
        await generate(_media_state(), config)


@pytest.mark.asyncio
async def test_fallback_node_with_media_without_reader_raises():
    config = {"configurable": {"model": MagicMock()}}
    state = _media_state()
    state["hits"] = []
    with pytest.raises(BadRequestError, match="media_reader"):
        await fallback(state, config)


@pytest.mark.asyncio
async def test_rag_answer_media_without_reader_raises():
    with patch(
        "miles_ai.rag.generate.answer.retrieve_hits",
        new_callable=AsyncMock,
        return_value=[],
    ):
        with pytest.raises(BadRequestError, match="media_reader"):
            await rag_answer(
                model=MagicMock(),
                system_prompt="sys",
                query="q",
                kb_ids=["kb1"],
                tenant_id=uuid4(),
                db=MagicMock(),
                media=[MediaRefIn(attachment_id=uuid4())],
            )
