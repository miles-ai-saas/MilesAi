"""``AgentChatEntryMixin.chat`` 的路由分发特征化测试。

``chat`` 是租户侧对话总入口，按 a2a_host / subagent / a2a_augmented / flow / rag
五条路由分发，且被 AFTER_CALL 与 ON_ERROR Hook、出站合规、调用记录包裹。此前该
函数无任何直接测试（仅有 ``chat_as_child_simple`` 的委托测试），本文件锁定其
路由选择、query 改写、异常收尾与清理行为，作为拆分重构的安全网。

测试绑定真实的 ``AgentChatEntryMixin.chat`` 与 ``AgentChatTurnMixin`` 的收尾方法，
仅替换外部服务（合规、Hook、调用记录、a2a/deepagents 运行时）。
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_core.models.agent import AgentStatus, AgentType
from miles_portal.tenant.agents.schemas.agent import ChatRequest
from miles_portal.tenant.agents.services.agent import chat_entry as entry_mod
from miles_portal.tenant.agents.services.agent.chat_entry import AgentChatEntryMixin
from miles_portal.tenant.agents.services.agent.chat_turn import AgentChatTurnMixin
from miles_portal.tenant.hooks.models import HookTrigger

AGENT_ID = uuid4()


# --- 替身 -------------------------------------------------------------------


class _Compliance:
    def __init__(self, db, ctx) -> None:  # noqa: ARG002
        _Compliance.last = self
        self.checked_in: list[str] = []
        self.checked_out: list[str] = []

    async def check_input(self, text, *, module):  # noqa: ANN001, ARG002
        self.checked_in.append(text)

    async def check_output(self, text, *, module):  # noqa: ANN001, ARG002
        self.checked_out.append(text)


class _Hooks:
    """记录 Hook 调用；BEFORE_CALL 可按 ``modified_query`` 改写 payload。"""

    modified_query: str | None = None

    def __init__(self, db, tenant_id) -> None:  # noqa: ARG002
        _Hooks.last = self
        self.calls: list[tuple] = []

    async def run(self, trigger, scope, target_id, payload):  # noqa: ANN001
        self.calls.append((trigger, scope, target_id, payload))
        if trigger is HookTrigger.BEFORE_CALL and _Hooks.modified_query is not None:
            return SimpleNamespace(payload={**payload, "query": _Hooks.modified_query})
        return SimpleNamespace(payload=payload)


class _Recorder:
    def __init__(self, db, ctx, *, agent_id, body, user_query, media_count=0) -> None:  # noqa: ARG002
        _Recorder.last = self
        self.user_query = user_query
        self.routes: list[str] = []
        self.successes: list[str] = []
        self.failures: list[tuple] = []

    def set_route(self, route):  # noqa: ANN001
        self.routes.append(route)

    async def record_success(self, response, *, route):  # noqa: ANN001
        self.successes.append(route)

    async def record_failure(self, exc, *, route, response=None):  # noqa: ANN001
        self.failures.append((route, exc))


class _FlowRepo:
    def __init__(self, *, flow=None, version=None) -> None:
        self._flow = flow
        self._version = version

    async def get_by_id(self, flow_id):  # noqa: ANN001, ARG002
        return self._flow

    async def get_version(self, flow_id, n):  # noqa: ANN001, ARG002
        return self._version


class _TxnDb:
    """最小事务替身：只记录收尾调用，供断言「谁在什么时候提交」。

    真实出口（``get_db`` 与 WS ``_run_chat_turn``）在异常时一律 rollback，
    因此这里把 commit/rollback 分开计数，才能分辨「提交了」还是「等着被回滚」。
    """

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class _Entry(SimpleNamespace):
    """最小入口替身：承载被绑定的真实方法，外部依赖走 fake。"""

    async def get_agent_or_raise(self, agent_id):  # noqa: ANN001, ARG002
        return self.agent

    async def maybe_augment_a2a(self, agent, body, response):  # noqa: ANN001, ARG002
        self.augmented += 1
        return response

    async def rag_chat(self, agent, body, kb_ids, top_k, agent_id, hooks, *, on_delta=None):  # noqa: ANN001
        self.rag_args = (kb_ids, top_k, agent_id)
        self.on_delta = on_delta
        return self.rag_response

    async def flow_run_context(self, agent, *, agent_id, inputs, kb_ids, media):  # noqa: ANN001, ARG002
        self.flow_inputs = inputs
        return {"inputs": inputs}


def _agent(**overrides):
    base = {
        "id": AGENT_ID,
        "status": AgentStatus.ENABLED,
        "agent_type": AgentType.CUSTOM,
        "published_flow_id": None,
        "knowledge_bases": [],
        "model_config_id": None,
        "model_config": object(),
        "config": {},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _entry(*, agent=None, flow_repo=None, rag_response=None):
    entry = _Entry(agent=agent or _agent(), db=_TxnDb(), ctx=SimpleNamespace(tenant_id=uuid4()))
    entry.augmented = 0
    entry.rag_args = None
    entry.flow_inputs = None
    entry.rag_response = rag_response or SimpleNamespace(answer="rag-answer")
    entry.flow_repo = flow_repo or _FlowRepo()
    # 绑定真实的收尾与路由解析，让 chat 的编排逻辑被真实执行
    for name in ("_finish_chat_turn", "_resolve_rag_route", "_complete_chat_turn"):
        setattr(entry, name, getattr(AgentChatTurnMixin, name).__get__(entry, type(entry)))
    entry._run_published_flow = AgentChatEntryMixin._run_published_flow.__get__(entry, type(entry))
    return entry


def _bind(entry):
    return AgentChatEntryMixin.chat.__get__(entry, type(entry))


@pytest.fixture(autouse=True)
def _patch_services(monkeypatch):
    """替换外部服务；每个用例复位类级配置，避免相互污染。"""
    _Hooks.modified_query = None
    _Hooks.last = None
    _Recorder.last = None
    monkeypatch.setattr(entry_mod, "ComplianceService", _Compliance)
    monkeypatch.setattr(entry_mod, "HookRunner", _Hooks)
    monkeypatch.setattr(entry_mod, "ChatCallRecorder", _Recorder)
    monkeypatch.setattr(entry_mod, "begin_chat_usage_accumulation", lambda: "acc")
    monkeypatch.setattr(entry_mod, "end_chat_usage_accumulation", lambda acc: None)
    monkeypatch.setattr(entry_mod, "set_generative_request_prefs", lambda **kw: None)
    monkeypatch.setattr(entry_mod, "clear_generative_request_prefs", lambda: None)
    monkeypatch.setattr(entry_mod, "user_requests_image_collage", lambda q: False)
    monkeypatch.setattr(entry_mod, "list_sub_agent_bindings", _async_ret([]))
    monkeypatch.setattr(entry_mod, "list_agent_a2a_peer_refs", _async_ret([]))


def _async_ret(value):
    async def _inner(*args, **kwargs):  # noqa: ANN001, ARG001
        return value

    return _inner


# --- 前置校验 ---------------------------------------------------------------


async def test_disabled_agent_is_rejected_before_any_hook(monkeypatch):
    entry = _entry(agent=_agent(status=AgentStatus.DISABLED))
    with pytest.raises(BadRequestError, match="已禁用"):
        await _bind(entry)(AGENT_ID, ChatRequest(query="hi"))
    assert _Hooks.last is None  # 未构造任何 Hook（亦未执行）


async def test_before_call_hook_rewrites_query(monkeypatch):
    _Hooks.modified_query = "改写后的 query"
    entry = _entry(agent=_agent(knowledge_bases=[]))
    await _bind(entry)(AGENT_ID, ChatRequest(query="原始"))
    assert _Compliance.last.checked_in == ["改写后的 query"]  # 合规校验的是改写后文本


async def test_media_only_query_becomes_placeholder(monkeypatch):
    entry = _entry()
    await _bind(entry)(AGENT_ID, ChatRequest(media=[{"attachment_id": uuid4()}]))
    assert _Recorder.last.user_query == "[附图]"


# --- 路由分发 ---------------------------------------------------------------


async def test_a2a_agent_routes_to_a2a_host(monkeypatch):
    called: list = []

    async def fake_host(service, agent, body):  # noqa: ANN001
        called.append(body.query)
        return SimpleNamespace(answer="a2a")

    import miles_portal.tenant.a2a.invoke as a2a_mod

    monkeypatch.setattr(a2a_mod, "run_a2a_host_chat", fake_host)
    entry = _entry(agent=_agent(agent_type=AgentType.A2A))
    resp = await _bind(entry)(AGENT_ID, ChatRequest(query="q"))

    assert resp.answer == "a2a"
    assert called == ["q"]
    assert _Recorder.last.routes == ["a2a_host"]
    assert _Recorder.last.successes == ["a2a_host"]


async def test_subagent_bindings_take_precedence_over_peers(monkeypatch):
    monkeypatch.setattr(entry_mod, "list_sub_agent_bindings", _async_ret([object()]))
    monkeypatch.setattr(entry_mod, "list_agent_a2a_peer_refs", _async_ret([object()]))

    import miles_integrations.deepagents.orchestrator as orch_mod

    async def fake_planned(service, agent, bindings, parent_input):  # noqa: ANN001
        return SimpleNamespace(answer="sub", steps=[{"s": 1}])

    monkeypatch.setattr(orch_mod, "run_subagent_planned_chat", fake_planned)
    entry = _entry()
    resp = await _bind(entry)(AGENT_ID, ChatRequest(query="q"))

    assert resp.answer == "sub"
    assert resp.steps == [{"s": 1}]
    assert _Recorder.last.routes == ["subagent"]
    assert entry.augmented == 1  # 有 peer_refs 时追加 a2a 增强


async def test_peers_without_bindings_route_to_a2a_augmented(monkeypatch):
    monkeypatch.setattr(entry_mod, "list_agent_a2a_peer_refs", _async_ret([object()]))
    called: dict = {}

    import miles_portal.tenant.a2a.invoke as a2a_mod

    async def fake_augmented(service, agent, body, *, kb_ids, top_k, agent_id, hooks):  # noqa: ANN001
        called.update(kb_ids=kb_ids, top_k=top_k, agent_id=agent_id, hooks=hooks)
        return SimpleNamespace(answer="aug", sources=[], steps=[])

    monkeypatch.setattr(a2a_mod, "run_a2a_augmented_chat", fake_augmented)
    entry = _entry(agent=_agent(knowledge_bases=[SimpleNamespace(id=uuid4())], config={"top_k": 7}))
    resp = await _bind(entry)(AGENT_ID, ChatRequest(query="q"))

    assert resp.answer == "aug"
    assert _Recorder.last.routes == ["a2a_augmented"]
    assert called["top_k"] == 7
    assert called["agent_id"] == AGENT_ID
    assert called["kb_ids"] == [str(entry.agent.knowledge_bases[0].id)]


async def test_published_flow_with_version_routes_to_flow(monkeypatch):
    flow_id = uuid4()
    version = SimpleNamespace(graph_json={"nodes": []})
    entry = _entry(flow_repo=_FlowRepo(flow=SimpleNamespace(id=flow_id, current_version=2), version=version))

    class _Runtime:
        async def run(self, graph, ctx):  # noqa: ANN001, ARG002
            return SimpleNamespace(output="flow-out", steps=[{"n": 1}])

    monkeypatch.setattr(entry_mod, "get_flow_runtime", lambda: _Runtime())
    entry.agent.published_flow_id = flow_id
    resp = await _bind(entry)(AGENT_ID, ChatRequest(query="q"))

    assert resp.answer == "flow-out"
    assert _Recorder.last.routes == ["flow"]
    assert entry.flow_inputs == {"query": "q"}
    assert entry.augmented == 1


async def test_flow_without_version_falls_back_to_rag(monkeypatch):
    entry = _entry(flow_repo=_FlowRepo(flow=None, version=None))
    entry.agent.published_flow_id = uuid4()
    await _bind(entry)(AGENT_ID, ChatRequest(query="q"))
    assert _Recorder.last.routes == ["direct_llm"]


async def test_flow_placeholder_input_requires_hook_to_blank_the_query(monkeypatch):
    """媒体-only 时 effective_query 为 ``[附图]``（非空），故不会走占位符分支；
    只有 BEFORE_CALL Hook 把 query 改写成空串，才会用「请根据附图回答。」兜底。
    """
    flow_id = uuid4()
    version = SimpleNamespace(graph_json={})
    entry = _entry(flow_repo=_FlowRepo(flow=SimpleNamespace(id=flow_id, current_version=1), version=version))

    class _Runtime:
        async def run(self, graph, ctx):  # noqa: ANN001, ARG002
            return SimpleNamespace(output="o", steps=[])

    monkeypatch.setattr(entry_mod, "get_flow_runtime", lambda: _Runtime())
    entry.agent.published_flow_id = flow_id
    _Hooks.modified_query = "   "  # Hook 把 query 清空
    await _bind(entry)(AGENT_ID, ChatRequest(media=[{"attachment_id": uuid4()}]))

    assert entry.flow_inputs["query"] == "请根据附图回答。"


async def test_flow_inputs_use_hook_rewritten_query(monkeypatch):
    """流程入参的 query 必须是 BEFORE_CALL Hook 改写后的版本，而非原始 body.query。"""
    flow_id = uuid4()
    version = SimpleNamespace(graph_json={})
    entry = _entry(flow_repo=_FlowRepo(flow=SimpleNamespace(id=flow_id, current_version=1), version=version))

    class _Runtime:
        async def run(self, graph, ctx):  # noqa: ANN001, ARG002
            return SimpleNamespace(output="o", steps=[])

    monkeypatch.setattr(entry_mod, "get_flow_runtime", lambda: _Runtime())
    entry.agent.published_flow_id = flow_id
    _Hooks.modified_query = "改写后的 query"

    await _bind(entry)(AGENT_ID, ChatRequest(query="原始 query"))

    assert entry.flow_inputs["query"] == "改写后的 query"


async def test_no_kb_no_tools_routes_direct_llm(monkeypatch):
    entry = _entry()
    await _bind(entry)(AGENT_ID, ChatRequest(query="q"))
    assert _Recorder.last.routes == ["direct_llm"]
    assert entry.rag_args == ([], 5, AGENT_ID)


async def test_tool_calling_flag_routes_tool_agent(monkeypatch):
    entry = _entry(agent=_agent(config={"enable_tool_calling": True}, model_config_id=uuid4()))
    await _bind(entry)(AGENT_ID, ChatRequest(query="q"))
    assert _Recorder.last.routes == ["tool_agent"]


async def test_rag_route_with_kb(monkeypatch):
    monkeypatch.setattr(
        "miles_portal.tenant.agents.services.agent.chat_turn.should_use_tools_with_kb",
        lambda agent, kb_ids: False,
    )
    monkeypatch.setattr(
        "miles_portal.tenant.agents.services.agent.chat_turn.should_use_langgraph_rag",
        lambda agent, *, kb_ids: True,
    )
    entry = _entry(agent=_agent(knowledge_bases=[SimpleNamespace(id=uuid4())], config={"top_k": 3}))
    await _bind(entry)(AGENT_ID, ChatRequest(query="q"))
    assert _Recorder.last.routes == ["rag"]
    assert entry.rag_args[1] == 3


# --- 收尾与异常 -------------------------------------------------------------


async def test_output_compliance_and_after_call_hook_run(monkeypatch):
    entry = _entry(rag_response=SimpleNamespace(answer="出站文本"))
    await _bind(entry)(AGENT_ID, ChatRequest(query="q"))

    assert _Compliance.last.checked_out == ["出站文本"]
    triggers = [c[0] for c in _Hooks.last.calls]
    assert HookTrigger.BEFORE_CALL in triggers
    assert HookTrigger.AFTER_CALL in triggers
    after = next(c for c in _Hooks.last.calls if c[0] is HookTrigger.AFTER_CALL)
    assert after[3]["direction"] == "out"
    assert after[3]["text"] == "出站文本"


async def test_after_call_hook_sees_query_rewritten_by_before_call(monkeypatch):
    """``finish`` 按引用捕获 ``hook_payload``，故 AFTER_CALL 必须拿到 Hook 改写后的版本。"""
    _Hooks.modified_query = "改写后的 query"
    entry = _entry()
    await _bind(entry)(AGENT_ID, ChatRequest(query="原始"))

    after = next(c for c in _Hooks.last.calls if c[0] is HookTrigger.AFTER_CALL)
    assert after[3]["query"] == "改写后的 query"
    before = next(c for c in _Hooks.last.calls if c[0] is HookTrigger.BEFORE_CALL)
    assert before[3]["query"] == "原始"  # 入站 Hook 看到的是改写前文本
    assert before[3]["direction"] == "in"


async def test_exception_records_failure_runs_on_error_hook_and_reraises(monkeypatch):
    entry = _entry()

    async def boom(agent, body, kb_ids, top_k, agent_id, hooks, *, on_delta=None):  # noqa: ANN001
        raise RuntimeError("rag 崩了")

    entry.rag_chat = boom
    with pytest.raises(RuntimeError, match="rag 崩了"):
        await _bind(entry)(AGENT_ID, ChatRequest(query="q"))

    assert _Recorder.last.failures[0][1].args[0] == "rag 崩了"
    on_error = [c for c in _Hooks.last.calls if c[0] is HookTrigger.ON_ERROR]
    assert len(on_error) == 1
    assert on_error[0][3]["error"] == "rag 崩了"


async def test_failure_audit_is_committed_before_reraising(monkeypatch):
    """回归：``record_failure`` 只 flush 不 commit，而两个出口在异常时都 rollback
    （``get_db`` 的 except 与 WS ``_run_chat_turn`` 的 except），于是失败与合规拦截的
    调用记录会被一起撤销——``AgentChatCall`` 里永远只有 success 行。失败审计必须
    在抛出前自己落库。
    """
    entry = _entry()

    async def boom(agent, body, kb_ids, top_k, agent_id, hooks, *, on_delta=None):  # noqa: ANN001
        raise BadRequestError("包含敏感词")

    entry.rag_chat = boom
    with pytest.raises(BadRequestError, match="敏感词"):
        await _bind(entry)(AGENT_ID, ChatRequest(query="q"))

    assert _Recorder.last.failures  # 确实记了失败
    assert entry.db.commits == 1  # 且必须提交，否则外层 rollback 会丢弃这条记录


async def test_success_path_leaves_commit_to_the_caller(monkeypatch):
    """成功路径不在 ``chat`` 内部提交：本轮落库仍由出口统一收尾成一个事务，
    避免把「调用记录 + 会话轮次」拆成两次提交。"""
    entry = _entry()
    await _bind(entry)(AGENT_ID, ChatRequest(query="q"))

    assert entry.db.commits == 0


async def test_failure_audit_commit_error_does_not_mask_original_exception(monkeypatch):
    """落库失败也不能换掉原始异常：调用方看到的原因必须是真实的业务失败。"""
    entry = _entry()

    class _BrokenDb(_TxnDb):
        async def commit(self) -> None:
            raise RuntimeError("连接已断")

    entry.db = _BrokenDb()

    async def boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise BadRequestError("包含敏感词")

    entry.rag_chat = boom
    with pytest.raises(BadRequestError, match="敏感词"):
        await _bind(entry)(AGENT_ID, ChatRequest(query="q"))


async def test_generative_prefs_are_cleared_even_on_failure(monkeypatch):
    cleared: list[bool] = []
    monkeypatch.setattr(entry_mod, "clear_generative_request_prefs", lambda: cleared.append(True))

    entry = _entry()

    async def boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("x")

    entry.rag_chat = boom
    with pytest.raises(RuntimeError):
        await _bind(entry)(AGENT_ID, ChatRequest(query="q"))
    assert cleared == [True]


async def test_on_delta_is_forwarded_to_rag_chat(monkeypatch):
    entry = _entry()

    async def fake_rag(agent, body, kb_ids, top_k, agent_id, hooks, *, on_delta=None):  # noqa: ANN001
        entry.on_delta = on_delta
        return SimpleNamespace(answer="ok")

    entry.rag_chat = fake_rag
    sentinel = object()
    await _bind(entry)(AGENT_ID, ChatRequest(query="q"), on_delta=sentinel)
    assert entry.on_delta is sentinel
