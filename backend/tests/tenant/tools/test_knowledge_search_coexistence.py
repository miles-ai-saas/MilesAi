"""knowledge_search 多库检索与绑定回退；loop 的 RAG 命中回填 sources，并验证
绑定 KB 时 knowledge_search 不受 tool_slugs 白名单过滤。
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_ai.integrations.langchain.tool_agent import loop as loop_mod
from miles_ai.integrations.langchain.tools import (
    get_platform_tools,
    make_builtin_tool,
    select_agent_tools,
)
from miles_core.models.agent.chat_io import ChatRequest
from miles_portal.tenant.tools.builtins import handlers as handlers_mod


class _Tool:
    def __init__(self, name: str) -> None:
        self.name = name


# --- 白名单与 KB 强制保留 ---


def test_select_agent_tools_always_allow_knowledge_search():
    tools = [_Tool("calculator"), _Tool("knowledge_search")]
    kept = select_agent_tools(tools, ["calculator"], always_allow={"knowledge_search"})
    assert [t.name for t in kept] == ["calculator", "knowledge_search"]


# --- 参数解析 ---


def test_resolve_kb_ids_variants():
    assert handlers_mod._resolve_kb_ids({"kb_ids": ["a", "b"]}) == ["a", "b"]
    assert handlers_mod._resolve_kb_ids({"kb_ids": "a, b ,a"}) == ["a", "b"]
    assert handlers_mod._resolve_kb_ids({"kb_id": "a"}) == ["a"]
    assert handlers_mod._resolve_kb_ids({"kb_ids": ["a"], "kb_id": "b"}) == ["a", "b"]
    assert handlers_mod._resolve_kb_ids({}) == []


# --- handler 多库 + 绑定回退 ---


async def test_handle_knowledge_search_uses_bound_kbs_and_top_k(monkeypatch):
    calls: dict = {}

    async def fake_retrieve_hits(query, *, tenant_id, kb_ids, db, top_k, bindings=None):  # noqa: ANN001
        calls.update({"query": query, "kb_ids": kb_ids, "top_k": top_k})
        return [{"score": 0.9, "content_preview": "hello"}]

    monkeypatch.setattr(handlers_mod, "retrieve_hits", fake_retrieve_hits)

    ctx = SimpleNamespace(tenant_id=uuid4())
    agent_cfg = {"_bound_kb_ids": ["kb-1", "kb-2"], "_bound_kb_top_k": 7}
    db = SimpleNamespace()

    async def fake_get(_model, _id, **kwargs):  # noqa: ANN001
        return SimpleNamespace(config=agent_cfg, knowledge_bases=[])

    db.get = fake_get

    out = await handlers_mod.handle_knowledge_search(
        {"query": "q"},
        db=db,
        ctx=ctx,
        agent_id=uuid4(),
    )
    assert calls == {"query": "q", "kb_ids": ["kb-1", "kb-2"], "top_k": 7}
    assert out["kb_ids"] == ["kb-1", "kb-2"]
    assert out["hit_count"] == 1


async def test_handle_knowledge_search_requires_kbs():
    db = SimpleNamespace()

    async def fake_get(_model, _id, **kwargs):  # noqa: ANN001
        return SimpleNamespace(config={}, knowledge_bases=[])

    db.get = fake_get
    with pytest.raises(Exception, match="knowledge_search"):
        await handlers_mod.handle_knowledge_search(
            {"query": "q"},
            db=db,
            ctx=SimpleNamespace(tenant_id=uuid4()),
            agent_id=uuid4(),
        )


# --- loop：命中回填 sources ---


class _Message:
    def __init__(self, content: str = "", tool_calls=None) -> None:
        self.content = content
        self.tool_calls = tool_calls


class _Choice:
    def __init__(self, message: _Message) -> None:
        self.message = message


class _Resp:
    def __init__(self, message: _Message) -> None:
        self.choices = [_Choice(message)]


class _ToolCall:
    def __init__(self, name: str, arguments: str) -> None:
        self.id = "call-1"
        self.function = SimpleNamespace(name=name, arguments=arguments)


class _Executor:
    async def meta(self, slug: str, *, tool_id=None) -> dict:  # noqa: ANN001
        return {"slug": slug, "name": slug, "require_confirmation": False, "source": "builtin"}

    async def invoke(self, slug: str, params, *, confirmed=False, tool_id=None) -> dict:  # noqa: ANN001
        return {"hits": [{"score": 0.8, "content_preview": "kb 片段"}], "kb_ids": ["kb-1"], "hit_count": 1}


async def test_loop_backfills_sources_and_keeps_knowledge_search(monkeypatch):
    captured: dict = {}
    responses = [
        _Resp(_Message("", tool_calls=[_ToolCall("knowledge_search", '{"query": "q"}')])),
        _Resp(_Message("依据片段作答。", tool_calls=[])),
    ]

    async def fake_litellm(model, messages, tools, *, temperature):  # noqa: ANN001
        captured["tools"] = tools
        return responses.pop(0)

    monkeypatch.setattr(loop_mod, "_litellm_with_tools", fake_litellm)

    agent = SimpleNamespace(
        model_config=object(),
        config={"tool_slugs": ["calculator"], "enable_tool_calling": True},
    )
    model = SimpleNamespace(model_type="chat")
    platform_tools = [*get_platform_tools()]  # 含 calculator / knowledge_search

    resp = await loop_mod.run_tool_calling_chat(
        agent,
        ChatRequest(query="知识库问题"),
        system_prompt="sys",
        model=model,
        tool_executor=_Executor(),
        platform_tools=platform_tools,
        media_reader=None,
        kb_ids=["kb-1"],
    )

    names = {t["function"]["name"] for t in captured["tools"]}
    assert {"calculator", "knowledge_search"} <= names
    assert resp.answer == "依据片段作答。"
    assert resp.sources == [{"score": 0.8, "content_preview": "kb 片段"}]


def test_make_knowledge_search_tool_schema_allows_kb_ids():
    schema = make_builtin_tool("knowledge_search").args_schema.model_json_schema()
    assert "kb_ids" in schema["properties"]
    assert schema["required"] == ["query"]
