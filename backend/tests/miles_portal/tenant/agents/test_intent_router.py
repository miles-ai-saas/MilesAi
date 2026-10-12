"""对话主路径独立意图识别层。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from miles_portal.tenant.agents.services.intent_router import (
    build_capability_catalog,
    chat_intent_router_enabled,
    parse_chat_intent,
    pick_top_level_route,
    recognize_chat_intent,
    should_skip_published_flow,
)


def test_parse_chat_intent_from_json():
    intent, reason = parse_chat_intent('{"intent":"rag","reason":"查库"}')
    assert intent == "rag"
    assert reason == "查库"


def test_parse_chat_intent_fenced_and_invalid():
    intent, _ = parse_chat_intent("```json\n{\"intent\":\"tools\"}\n```")
    assert intent == "tools"
    assert parse_chat_intent("not-json")[0] == "auto"
    assert parse_chat_intent('{"intent":"evil"}')[0] == "auto"


def test_chat_intent_router_enabled():
    assert chat_intent_router_enabled(SimpleNamespace(config={})) is False
    assert chat_intent_router_enabled(SimpleNamespace(config={"chat_intent_router": {"enabled": True}})) is True


def test_build_capability_catalog_and_pick_route():
    catalog = build_capability_catalog(
        has_model=True,
        has_kb=True,
        tools_enabled=True,
        has_flow=True,
        has_subagents=True,
        has_a2a_peers=True,
    )
    intents = {c["intent"] for c in catalog}
    assert intents >= {"direct", "rag", "tools", "flow", "subagent", "a2a", "auto"}

    assert pick_top_level_route(preferred="rag", has_bindings=True, has_peer_refs=True) == "local"
    assert pick_top_level_route(preferred="subagent", has_bindings=True, has_peer_refs=False) == "subagent"
    assert pick_top_level_route(preferred="a2a", has_bindings=True, has_peer_refs=True) == "a2a_augmented"
    assert pick_top_level_route(preferred="auto", has_bindings=True, has_peer_refs=False) == "subagent"
    assert pick_top_level_route(preferred="auto", has_bindings=False, has_peer_refs=True) == "a2a_augmented"
    assert should_skip_published_flow("tools") is True
    assert should_skip_published_flow("flow") is False


@pytest.mark.asyncio
async def test_recognize_chat_intent_calls_llm():
    agent = SimpleNamespace(id=uuid4(), model_config=object(), config={})
    catalog = build_capability_catalog(
        has_model=True,
        has_kb=True,
        tools_enabled=False,
        has_flow=False,
        has_subagents=False,
        has_a2a_peers=False,
    )
    db = AsyncMock()
    model = MagicMock()

    with (
        patch(
            "miles_portal.tenant.agents.services.intent_router.resolve_model_for_invoke",
            new=AsyncMock(return_value=model),
        ),
        patch(
            "miles_portal.tenant.agents.services.intent_router.ainvoke_chat",
            new=AsyncMock(return_value='{"intent":"rag","reason":"kb"}'),
        ),
    ):
        intent, meta = await recognize_chat_intent(
            agent,
            "公司制度是什么",
            catalog=catalog,
            db=db,
            tenant_id=uuid4(),
            model_override=agent.model_config,
        )
    assert intent == "rag"
    assert meta["intent"] == "rag"
    assert meta["engine"] == "intent_llm"
