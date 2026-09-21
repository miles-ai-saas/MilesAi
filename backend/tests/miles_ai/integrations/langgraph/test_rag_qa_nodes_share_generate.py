"""rag_qa 的 generate / fallback 必须复用无 db 的生成入口。

两节点原先各自复制了一份「拼 prompt + 解析附图 + ainvoke_chat」，既要维护两处，
又都绕过生成入口的签名约束。这里证明两者都走 generate_rag_answer。
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

import miles_ai.integrations.langgraph.graphs.rag_qa as rag_qa_mod
from miles_ai.integrations.langgraph.graphs.rag_qa import fallback, generate, retrieve


class _RecordingShortSession:
    """假 AsyncSessionLocal：记录开合次数并交出可辨识的 db。"""

    def __init__(self) -> None:
        self.db = object()
        self.entered = 0
        self.exited = 0

    async def __aenter__(self) -> object:
        self.entered += 1
        return self.db

    async def __aexit__(self, *exc: object) -> bool:
        self.exited += 1
        return False


def _state(*, hits: list | None = None) -> dict:
    return {
        "tenant_id": str(uuid4()),
        "system_prompt": "你是助手",
        "query": "检索词",
        "prompt_query": "生成问题",
        "hits": hits if hits is not None else [{"content_preview": "片段", "score": 0.9}],
        "temperature": 0.7,
    }


@pytest.mark.asyncio
async def test_generate_node_uses_generate_rag_answer():
    config = {"configurable": {"model": MagicMock()}}
    with patch(
        "miles_ai.integrations.langgraph.graphs.rag_qa.generate_rag_answer",
        new_callable=AsyncMock,
        return_value="答案",
    ) as mock_gen:
        out = await generate(_state(), config)

    assert out["answer"] == "答案"
    mock_gen.assert_awaited_once()
    prompt = mock_gen.await_args.kwargs["prompt"]
    assert "片段" in prompt
    assert mock_gen.await_args.kwargs["media"] is None


@pytest.mark.asyncio
async def test_fallback_node_uses_generate_rag_answer():
    config = {"configurable": {"model": MagicMock()}}
    with patch(
        "miles_ai.integrations.langgraph.graphs.rag_qa.generate_rag_answer",
        new_callable=AsyncMock,
        return_value="兜底",
    ) as mock_gen:
        out = await fallback(_state(hits=[]), config)

    assert out["answer"] == "兜底"
    mock_gen.assert_awaited_once()
    prompt = mock_gen.await_args.kwargs["prompt"]
    assert "未检索到" in prompt


@pytest.mark.asyncio
async def test_generate_node_passes_hits_prompt_for_low_relevance_fallback():
    """fallback 有命中时用「相关性较低」话术（与 generate 的正常 prompt 区分）。"""
    config = {"configurable": {"model": MagicMock()}}
    with patch(
        "miles_ai.integrations.langgraph.graphs.rag_qa.generate_rag_answer",
        new_callable=AsyncMock,
        return_value="兜底",
    ) as mock_gen:
        await fallback(_state(), config)

    prompt = mock_gen.await_args.kwargs["prompt"]
    assert "相关性较低" in prompt


@pytest.mark.asyncio
async def test_retrieve_node_retrieves_on_its_own_session(monkeypatch):
    """检索节点：检索在自开的一次会话上进行，steps 汇总照常产出。"""
    short = _RecordingShortSession()
    monkeypatch.setattr(rag_qa_mod, "AsyncSessionLocal", lambda: short)

    seen: list[tuple[str, object]] = []

    async def fake_retrieve_hits(query, *, tenant_id, kb_ids, db, top_k, bindings):
        seen.append((query, db))
        return [{"content_preview": "片段", "score": 0.9}]

    monkeypatch.setattr(rag_qa_mod, "retrieve_hits", fake_retrieve_hits)

    state = {
        "tenant_id": str(uuid4()),
        "query": "检索词",
        "kb_ids": ["kb-1"],
        "top_k": 5,
    }
    config = {"configurable": {"kb_retrieval": object()}}

    out = await retrieve(state, config)

    assert out["hits"] == [{"content_preview": "片段", "score": 0.9}]
    assert out["steps"][0]["node"] == "retrieve"
    assert out["steps"][0]["hit_count"] == 1
    assert out["steps"][0]["top_score"] == 0.9
    assert seen == [("检索词", short.db)]
    assert (short.entered, short.exited) == (1, 1)
