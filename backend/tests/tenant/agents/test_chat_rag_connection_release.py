"""RAG 生成阶段释放请求会话连接（编排级）。

靠三件事达成：检索与附图解析走短会话、生成前 commit 请求会话、生成入口不含 db。
本文件从 L1 视角断言前两件（第三件见 tests/rag/test_generate_rag_answer.py）。
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from miles_portal.tenant.agents.schemas.agent import ChatRequest
from miles_portal.tenant.agents.services.agent import chat_rag as chat_rag_mod
from miles_portal.tenant.agents.services.agent.chat_rag import AgentChatRagMixin
from miles_portal.tenant.attachments.services.media_reader import FlowMediaReader


class _TxnDb:
    """记录收尾动作与生成调用次序的最小事务替身。"""

    def __init__(self) -> None:
        self.events: list[str] = []

    async def commit(self) -> None:
        self.events.append("commit")

    async def rollback(self) -> None:
        self.events.append("rollback")


class _ShortSession:
    """AsyncSessionLocal 替身：记录被开过几次。"""

    def __init__(self) -> None:
        self.entered = 0

    async def __aenter__(self) -> "_ShortSession":
        self.entered += 1
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


def _run(coro):
    return asyncio.run(coro)


def _svc(db, *, media_query: str = "问题") -> SimpleNamespace:
    async def resolve_system_prompt(agent):
        return "sys"

    async def resolve_invoke_model(cfg):
        return MagicMock()

    async def resolve_chat_media_parts(agent, body):
        return media_query, []

    return SimpleNamespace(
        db=db,
        ctx=SimpleNamespace(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions=frozenset(["agent:chat"]),
            is_superuser=False,
        ),
        resolve_system_prompt=resolve_system_prompt,
        resolve_invoke_model=resolve_invoke_model,
        resolve_chat_media_parts=resolve_chat_media_parts,
        chat_usage_sink=lambda model, source_id=None: MagicMock(),
    )


def _agent() -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=uuid4(),
        model_config_id=uuid4(),
        model_config=MagicMock(),
        config={"temperature": 0.7},
    )


def _hooks(*, payload: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(payload=payload or {})))


def test_linear_path_retrieves_in_short_session_then_commits_before_generate(monkeypatch):
    db = _TxnDb()
    short = _ShortSession()
    svc = _svc(db)
    captured: dict[str, object] = {}

    async def fake_retrieve(*args, **kwargs):
        captured["retrieve_db"] = kwargs["db"]
        return [{"content_preview": "片段", "score": 0.9}]

    async def fake_generate(**kwargs):
        db.events.append("generate")
        captured["generate_kwargs"] = kwargs
        return "答"

    monkeypatch.setattr(chat_rag_mod, "AsyncSessionLocal", lambda: short)
    monkeypatch.setattr(chat_rag_mod, "build_kb_retrieval_bindings", lambda: MagicMock())
    monkeypatch.setattr(chat_rag_mod, "should_use_tools_with_kb", lambda *a, **k: False)
    monkeypatch.setattr(chat_rag_mod, "should_use_langgraph_rag", lambda *a, **k: False)
    monkeypatch.setattr(chat_rag_mod, "retrieve_hits", AsyncMock(side_effect=fake_retrieve))
    monkeypatch.setattr(chat_rag_mod, "generate_rag_answer", AsyncMock(side_effect=fake_generate))

    out = _run(
        AgentChatRagMixin.rag_chat(
            svc,
            _agent(),
            ChatRequest(query="问题"),
            ["kb1"],
            5,
            uuid4(),
            _hooks(),
        )
    )

    assert out.answer == "答"
    # 检索走的是短会话，不是请求会话
    assert captured["retrieve_db"] is short
    assert short.entered == 1
    # 顺序：先 commit 请求会话，再进入生成
    assert db.events == ["commit", "generate"]
    # 生成入口拿到的是 hits，不拿 db
    assert captured["generate_kwargs"]["prompt"].endswith("问题")
    assert "db" not in captured["generate_kwargs"]


def test_linear_path_media_reader_is_short_session_reader(monkeypatch):
    db = _TxnDb()
    svc = _svc(db)
    monkeypatch.setattr(chat_rag_mod, "AsyncSessionLocal", lambda: _ShortSession())
    monkeypatch.setattr(chat_rag_mod, "build_kb_retrieval_bindings", lambda: MagicMock())
    monkeypatch.setattr(chat_rag_mod, "should_use_tools_with_kb", lambda *a, **k: False)
    monkeypatch.setattr(chat_rag_mod, "should_use_langgraph_rag", lambda *a, **k: False)
    monkeypatch.setattr(chat_rag_mod, "retrieve_hits", AsyncMock(return_value=[]))
    monkeypatch.setattr(chat_rag_mod, "generate_rag_answer", AsyncMock(return_value="答"))

    _run(AgentChatRagMixin.rag_chat(svc, _agent(), ChatRequest(query="问题"), ["kb1"], 5, uuid4(), _hooks()))

    reader = chat_rag_mod.generate_rag_answer.await_args.kwargs["media_reader"]
    assert isinstance(reader, FlowMediaReader)


def test_linear_path_keeps_retrieve_query_and_prompt_query_distinct(monkeypatch):
    """回归：检索用 retrieve_query、prompt 用 prompt_query，两者不得对调。

    当 BEFORE_CALL Hook 把 query 改写成空白、且带附图时，两条用途会真正分叉：
    retrieve_query 兜底为 body.query，prompt_query 兜底为附图文案。
    """
    db = _TxnDb()
    short = _ShortSession()
    svc = _svc(db, media_query="请根据附图回答。")
    captured: dict[str, object] = {}

    async def fake_retrieve(query, **kwargs):
        captured["search"] = query
        return []

    def fake_build_prompt(**kwargs):
        captured["prompt_kwargs"] = kwargs
        return "拼好的 prompt"

    monkeypatch.setattr(chat_rag_mod, "AsyncSessionLocal", lambda: short)
    monkeypatch.setattr(chat_rag_mod, "build_kb_retrieval_bindings", lambda: MagicMock())
    monkeypatch.setattr(chat_rag_mod, "should_use_tools_with_kb", lambda *a, **k: False)
    monkeypatch.setattr(chat_rag_mod, "should_use_langgraph_rag", lambda *a, **k: False)
    monkeypatch.setattr(chat_rag_mod, "retrieve_hits", AsyncMock(side_effect=fake_retrieve))
    monkeypatch.setattr(chat_rag_mod, "build_rag_prompt", fake_build_prompt)
    monkeypatch.setattr(chat_rag_mod, "generate_rag_answer", AsyncMock(return_value="答"))

    _run(
        AgentChatRagMixin.rag_chat(
            svc,
            _agent(),
            ChatRequest(query="原始问题"),
            ["kb1"],
            5,
            uuid4(),
            _hooks(payload={"query": "   "}),
        )
    )

    assert captured["search"] == "原始问题"
    assert captured["prompt_kwargs"]["query"] == "请根据附图回答。"


def test_graph_path_commits_before_workflow(monkeypatch):
    db = _TxnDb()
    svc = _svc(db)

    async def fake_workflow(**kwargs):
        db.events.append("workflow")
        return "答", [], []

    monkeypatch.setattr(chat_rag_mod, "build_kb_retrieval_bindings", lambda: MagicMock())
    monkeypatch.setattr(chat_rag_mod, "should_use_tools_with_kb", lambda *a, **k: False)
    monkeypatch.setattr(chat_rag_mod, "should_use_langgraph_rag", lambda *a, **k: True)
    monkeypatch.setattr(chat_rag_mod, "run_rag_workflow", AsyncMock(side_effect=fake_workflow))

    _run(AgentChatRagMixin.rag_chat(svc, _agent(), ChatRequest(query="问题"), ["kb1"], 5, uuid4(), _hooks()))

    assert db.events == ["commit", "workflow"]
    reader = chat_rag_mod.run_rag_workflow.await_args.kwargs["media_reader"]
    assert isinstance(reader, FlowMediaReader)


def test_direct_chat_commits_before_llm(monkeypatch):
    db = _TxnDb()
    svc = _svc(db)
    captured: dict[str, object] = {}

    async def fake_ainvoke(model, messages, **kwargs):
        db.events.append("llm")
        captured["messages"] = messages
        return "答"

    monkeypatch.setattr(chat_rag_mod, "ainvoke_chat", AsyncMock(side_effect=fake_ainvoke))

    out = _run(
        AgentChatRagMixin.direct_chat(
            svc,
            _agent(),
            ChatRequest(query="问题"),
            uuid4(),
            _hooks(),
        )
    )

    assert out.answer == "答"
    assert db.events == ["commit", "llm"]
