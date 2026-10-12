"""RAG 生成阶段释放请求会话连接（编排级）。

靠三件事达成：检索与附图解析各自新开会话、生成前 commit 请求会话、生成入口不含 db。
本文件从 L1 视角断言前两件（第三件见 tests/miles_ai/rag/test_generate_rag_answer.py）。
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from miles_portal.tenant.agents.schemas.agent import ChatRequest
from miles_portal.tenant.agents.services.agent import chat_direct as chat_direct_mod
from miles_portal.tenant.agents.services.agent import chat_rag as chat_rag_mod
from miles_portal.tenant.agents.services.agent.chat_rag import AgentChatRagMixin
from miles_portal.tenant.attachments.services.media_reader import FlowMediaReader


class _TxnDb:
    """记录收尾动作与生成调用次序的最小事务替身。"""

    def __init__(self) -> None:
        self.events: list[str] = []

    def expunge(self, obj: object) -> None:
        self.events.append("expunge")

    async def commit(self) -> None:
        self.events.append("commit")

    async def rollback(self) -> None:
        self.events.append("rollback")


class _ShortSession:
    """``AsyncSessionLocal`` 替身：记录被开过几次、是否已退出。

    传入 ``events`` 时向共享事件流追加 ``short_enter`` / ``short_exit``，用于断言
    短会话没有把 LLM 调用包在里面（短会话包住生成 = 生成期间仍占一个连接）。
    """

    def __init__(self, events: list[str] | None = None) -> None:
        self.entered = 0
        self.exited = 0
        self._events = events

    async def __aenter__(self) -> "_ShortSession":
        self.entered += 1
        if self._events is not None:
            self._events.append("short_enter")
        return self

    async def __aexit__(self, *exc: object) -> bool:
        self.exited += 1
        if self._events is not None:
            self._events.append("short_exit")
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


def _patch_chat_memory(monkeypatch, history=None):  # noqa: ANN001
    monkeypatch.setattr(
        chat_rag_mod,
        "load_chat_history_messages",
        AsyncMock(return_value=history if history is not None else []),
    )


def test_linear_path_retrieves_in_short_session_then_commits_before_generate(monkeypatch):
    db = _TxnDb()
    short = _ShortSession(events=db.events)
    svc = _svc(db)
    captured: dict[str, object] = {}

    async def fake_retrieve(*args, **kwargs):
        captured["retrieve_db"] = kwargs["db"]
        return [{"content_preview": "片段", "score": 0.9}]

    async def fake_generate(**kwargs):
        db.events.append("generate")
        captured["generate_kwargs"] = kwargs
        return "答"

    _patch_chat_memory(monkeypatch)
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
    assert short.exited == 1
    # 顺序：短会话已退出 → 请求会话 commit → 才进入生成。
    # 短会话若包住 LLM 调用，生成期间就仍占着一个连接（M17 指出的护栏缺口）。
    assert db.events == ["short_enter", "short_exit", "commit", "generate"]
    # 生成入口拿到的是 hits，不拿 db
    assert captured["generate_kwargs"]["prompt"].endswith("问题")
    assert "db" not in captured["generate_kwargs"]


def test_linear_path_media_reader_is_short_session_reader(monkeypatch):
    db = _TxnDb()
    svc = _svc(db)
    _patch_chat_memory(monkeypatch)
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

    _patch_chat_memory(monkeypatch)
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

    _patch_chat_memory(
        monkeypatch,
        history=[{"role": "user", "content": "上次问了什么"}],
    )
    monkeypatch.setattr(chat_rag_mod, "build_kb_retrieval_bindings", lambda: MagicMock())
    monkeypatch.setattr(chat_rag_mod, "should_use_tools_with_kb", lambda *a, **k: False)
    monkeypatch.setattr(chat_rag_mod, "should_use_langgraph_rag", lambda *a, **k: True)
    monkeypatch.setattr(chat_rag_mod, "run_rag_workflow", AsyncMock(side_effect=fake_workflow))

    out = _run(
        AgentChatRagMixin.rag_chat(
            svc,
            _agent(),
            ChatRequest(query="问题", conversation_id="conv-rag"),
            ["kb1"],
            5,
            uuid4(),
            _hooks(),
        )
    )

    assert db.events == ["commit", "workflow"]
    kwargs = chat_rag_mod.run_rag_workflow.await_args.kwargs
    assert "【近期对话】" in kwargs["system_prompt"]
    assert "上次问了什么" in kwargs["system_prompt"]
    assert isinstance(kwargs["media_reader"], FlowMediaReader)
    assert any(s.get("type") == "chat_memory" and s.get("history_messages") == 1 for s in out.steps)


def test_linear_path_injects_history_into_system_prompt(monkeypatch):
    db = _TxnDb()
    short = _ShortSession()
    svc = _svc(db)
    captured: dict[str, object] = {}

    def fake_build_prompt(**kwargs):
        captured["prompt_kwargs"] = kwargs
        return "拼好的 prompt"

    _patch_chat_memory(
        monkeypatch,
        history=[
            {"role": "user", "content": "上一轮"},
            {"role": "assistant", "content": "上一答"},
        ],
    )
    monkeypatch.setattr(chat_rag_mod, "AsyncSessionLocal", lambda: short)
    monkeypatch.setattr(chat_rag_mod, "build_kb_retrieval_bindings", lambda: MagicMock())
    monkeypatch.setattr(chat_rag_mod, "should_use_tools_with_kb", lambda *a, **k: False)
    monkeypatch.setattr(chat_rag_mod, "should_use_langgraph_rag", lambda *a, **k: False)
    monkeypatch.setattr(chat_rag_mod, "retrieve_hits", AsyncMock(return_value=[]))
    monkeypatch.setattr(chat_rag_mod, "build_rag_prompt", fake_build_prompt)
    monkeypatch.setattr(chat_rag_mod, "generate_rag_answer", AsyncMock(return_value="答"))

    out = _run(
        AgentChatRagMixin.rag_chat(
            svc,
            _agent(),
            ChatRequest(query="本轮", conversation_id="conv-1"),
            ["kb1"],
            5,
            uuid4(),
            _hooks(),
        )
    )

    system = captured["prompt_kwargs"]["system_prompt"]
    assert "【近期对话】" in system
    assert "上一轮" in system
    assert out.steps[0].get("history_messages") == 2


def test_direct_chat_commits_before_llm(monkeypatch):
    db = _TxnDb()
    svc = _svc(db)
    captured: dict[str, object] = {}

    async def fake_ainvoke(model, messages, **kwargs):
        db.events.append("llm")
        captured["messages"] = messages
        return "答"

    monkeypatch.setattr(chat_direct_mod, "ainvoke_chat", AsyncMock(side_effect=fake_ainvoke))
    monkeypatch.setattr(
        chat_direct_mod,
        "load_chat_history_messages",
        AsyncMock(return_value=[{"role": "user", "content": "上一轮"}]),
    )

    out = _run(
        AgentChatRagMixin.direct_chat(
            svc,
            _agent(),
            ChatRequest(query="问题", conversation_id="conv-1"),
            uuid4(),
            _hooks(),
        )
    )

    assert out.answer == "答"
    assert db.events == ["commit", "llm"]
    roles = [m["role"] for m in captured["messages"]]
    assert roles == ["system", "user", "user"]
    assert captured["messages"][1]["content"] == "上一轮"
    assert out.steps[0].get("history_messages") == 1


def _tool_agent() -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=uuid4(),
        model_config_id=uuid4(),
        model_config=MagicMock(),
        config={"enable_tool_calling": True},
    )


def test_tool_agent_commits_before_run_tool_calling_chat(monkeypatch):
    """装配完成后 expunge 再 commit，避免 ephemeral config flush；再进入 tool 循环。"""
    db = _TxnDb()
    svc = _svc(db)
    agent = _tool_agent()
    captured: dict[str, object] = {}

    async def fake_assemble(*args, **kwargs):
        db.events.append("assemble")
        return []

    async def fake_run_tool_calling_chat(agent_arg, *args, **kwargs):
        db.events.append("tool_loop")
        captured["agent"] = agent_arg
        captured["kwargs"] = kwargs
        return MagicMock(answer="答", sources=[], steps=[])

    monkeypatch.setattr(
        "miles_portal.tenant.tools.services.agent_tool_assembly.assemble_agent_tools",
        fake_assemble,
    )
    monkeypatch.setattr(
        "miles_integrations.langchain.tool_agent.run_tool_calling_chat",
        fake_run_tool_calling_chat,
    )
    monkeypatch.setattr(
        chat_direct_mod,
        "load_chat_history_messages",
        AsyncMock(return_value=[{"role": "assistant", "content": "先前答复"}]),
    )

    out = _run(
        AgentChatRagMixin._run_tool_agent(
            svc,
            agent,
            ChatRequest(query="问题", conversation_id="conv-1"),
            agent_id=uuid4(),
            system_prompt="sys",
            kb_ids=["kb1"],
            kb_top_k=3,
        )
    )

    assert out.answer == "答"
    assert db.events == ["assemble", "expunge", "commit", "tool_loop"]
    # 内存对象仍带 ephemeral keys，供 run_tool_calling_chat 使用
    assert captured["agent"] is agent
    assert agent.config.get("_conversation_id") == "conv-1"
    assert agent.config.get("_bound_kb_ids") == ["kb1"]
    assert agent.config.get("_bound_kb_top_k") == 3
    assert captured["kwargs"]["history_messages"] == [{"role": "assistant", "content": "先前答复"}]


def test_tool_agent_uses_flow_media_reader_and_short_session_executor(monkeypatch):
    """tool_agent 循环用 FlowMediaReader + 短会话 executor，不占用请求会话。"""
    from miles_portal.tenant.tools.services.agent_executor import ShortSessionAgentToolExecutor

    db = _TxnDb()
    svc = _svc(db)
    captured: dict[str, object] = {}

    async def fake_assemble(*args, **kwargs):
        return []

    async def fake_run_tool_calling_chat(*args, **kwargs):
        captured["kwargs"] = kwargs
        return MagicMock(answer="答", sources=[], steps=[])

    monkeypatch.setattr(
        "miles_portal.tenant.tools.services.agent_tool_assembly.assemble_agent_tools",
        fake_assemble,
    )
    monkeypatch.setattr(
        "miles_integrations.langchain.tool_agent.run_tool_calling_chat",
        fake_run_tool_calling_chat,
    )
    monkeypatch.setattr(chat_direct_mod, "load_chat_history_messages", AsyncMock(return_value=[]))

    _run(
        AgentChatRagMixin._run_tool_agent(
            svc,
            _tool_agent(),
            ChatRequest(query="问题"),
            agent_id=uuid4(),
            system_prompt="sys",
        )
    )

    assert isinstance(captured["kwargs"]["media_reader"], FlowMediaReader)
    assert isinstance(captured["kwargs"]["tool_executor"], ShortSessionAgentToolExecutor)
