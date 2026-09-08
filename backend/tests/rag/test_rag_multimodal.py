"""RAG 生成阶段多模态（检索仍文本 query）。"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.common.schemas.media import MediaRefIn
from app.core.tenant import TenantContext
from app.integrations.chat.multimodal import build_invoke_messages_with_media
from app.integrations.langgraph.graphs.rag_qa import _prompt_user_query, generate
from app.integrations.langgraph.runner import run_rag_workflow


def test_prompt_user_query_prefers_prompt_query():
    state = {"query": "检索用", "prompt_query": "生成用"}
    assert _prompt_user_query(state) == "生成用"


@pytest.mark.asyncio
async def test_build_invoke_messages_with_media():
    ctx = TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="t",
        is_superuser=False,
        permissions=frozenset(),
    )
    att_id = uuid4()
    with patch(
        "app.integrations.chat.multimodal.resolve_media_refs",
        new_callable=AsyncMock,
        return_value=[{"type": "image_url", "image_url": {"url": "data:image/png;base64,x"}}],
    ):
        msgs = await build_invoke_messages_with_media(
            AsyncMock(),
            ctx,
            prompt_text="参考：...\n\n用户问题：看图",
            media=[MediaRefIn(attachment_id=att_id)],
        )
    assert isinstance(msgs[0]["content"], list)


@pytest.mark.asyncio
async def test_generate_node_with_media():
    tenant_id = uuid4()
    user_id = uuid4()
    model = MagicMock()
    state = {
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "system_prompt": "你是助手",
        "query": "检索词",
        "prompt_query": "描述图片",
        "hits": [{"content": "片段", "score": 0.9}],
        "temperature": 0.7,
        "media": [{"attachment_id": str(uuid4()), "detail": "auto"}],
    }
    config = {"configurable": {"model": model}}

    with (
        patch(
            "app.integrations.langgraph.graphs.rag_qa.build_invoke_messages_with_media",
            new_callable=AsyncMock,
            return_value=[{"role": "user", "content": [{"type": "text", "text": "x"}]}],
        ) as mock_build,
        patch(
            "app.integrations.langgraph.graphs.rag_qa.ainvoke_chat",
            new_callable=AsyncMock,
            return_value="答案",
        ),
        patch("app.integrations.langgraph.graphs.rag_qa.AsyncSessionLocal") as session_cls,
    ):
        db = MagicMock()
        session_cls.return_value.__aenter__ = AsyncMock(return_value=db)
        session_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        out = await generate(state, config)

    assert out["answer"] == "答案"
    mock_build.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_rag_workflow_passes_media_in_initial():
    model = MagicMock()
    att_id = uuid4()
    uid = uuid4()
    tid = uuid4()
    aid = uuid4()

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={"answer": "ok", "hits": [], "steps": []},
    )

    with patch(
        "app.integrations.langgraph.runner.get_compiled_rag_graph",
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
            user_id=uid,
        )

    initial = mock_graph.ainvoke.await_args.args[0]
    assert initial["query"] == "检索"
    assert initial["prompt_query"] == "生成问题"
    assert len(initial["media"]) == 1
    assert initial["user_id"] == str(uid)
