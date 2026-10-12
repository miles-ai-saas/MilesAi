"""流程 LLMCall on_delta：仅答案产出节点透传。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from miles_ai.flow_runtime.compiler.report import resolve_node_type
from miles_ai.flow_runtime.graph_analysis import find_answer_stream_llm_nodes
from miles_ai.flow_runtime.nodes.llm_nodes import llm_call
from miles_ai.flow_runtime.types import FlowGraph, RunContext


def test_find_answer_stream_llm_end_node():
    fg = FlowGraph.from_dict(
        {
            "nodes": [
                {"id": "s", "type": "Start", "data": {}},
                {"id": "llm", "type": "LLMCall", "data": {}},
            ],
            "edges": [{"source": "s", "target": "llm"}],
        }
    )
    assert find_answer_stream_llm_nodes(fg, resolve_node_type) == frozenset({"llm"})


def test_find_answer_stream_llm_feeding_text_output():
    fg = FlowGraph.from_dict(
        {
            "nodes": [
                {"id": "llm", "type": "LLMCall", "data": {}},
                {"id": "out", "type": "TextOutput", "data": {}},
            ],
            "edges": [{"source": "llm", "target": "out"}],
        }
    )
    assert find_answer_stream_llm_nodes(fg, resolve_node_type) == frozenset({"llm"})


def test_find_answer_stream_skips_intermediate_llm():
    fg = FlowGraph.from_dict(
        {
            "nodes": [
                {"id": "a", "type": "LLMCall", "data": {}},
                {"id": "b", "type": "LLMCall", "data": {}},
            ],
            "edges": [{"source": "a", "target": "b"}],
        }
    )
    assert find_answer_stream_llm_nodes(fg, resolve_node_type) == frozenset({"b"})


@pytest.mark.asyncio
async def test_llm_call_forwards_on_delta_when_node_allowed():
    deltas: list[str] = []

    async def on_delta(text: str) -> None:
        deltas.append(text)

    async def fake_resolve(_mid: str):
        return SimpleNamespace(id=uuid4(), model_type="chat", api_key_encrypted=None)

    ctx = RunContext(
        tenant_id=str(uuid4()),
        model_config_id=str(uuid4()),
        executing_node_id="llm-end",
        on_delta=on_delta,
        answer_stream_node_ids=frozenset({"llm-end"}),
        resolve_model=fake_resolve,
    )

    with patch(
        "miles_ai.flow_runtime.nodes.llm_nodes.ainvoke_chat",
        new_callable=AsyncMock,
        return_value="ok",
    ) as mock_chat:
        out = await llm_call({}, {"prompt": "hi"}, ctx)

    assert out == "ok"
    assert mock_chat.await_args.kwargs["on_delta"] is on_delta


@pytest.mark.asyncio
async def test_llm_call_skips_on_delta_for_intermediate_node():
    async def on_delta(text: str) -> None:
        return None

    async def fake_resolve(_mid: str):
        return SimpleNamespace(id=uuid4(), model_type="chat", api_key_encrypted=None)

    ctx = RunContext(
        tenant_id=str(uuid4()),
        model_config_id=str(uuid4()),
        executing_node_id="llm-mid",
        on_delta=on_delta,
        answer_stream_node_ids=frozenset({"llm-end"}),
        resolve_model=fake_resolve,
    )

    with patch(
        "miles_ai.flow_runtime.nodes.llm_nodes.ainvoke_chat",
        new_callable=AsyncMock,
        return_value="ok",
    ) as mock_chat:
        await llm_call({}, {"prompt": "hi"}, ctx)

    assert mock_chat.await_args.kwargs["on_delta"] is None
