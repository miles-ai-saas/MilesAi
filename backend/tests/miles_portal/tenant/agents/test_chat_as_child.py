"""``AgentChatEntryMixin.chat_as_child`` 的特征化测试。

该入口（子智能体工位）只走「已发布流程 / RAG 直连」两条路由，此前仅有
``chat_as_child_simple`` 的委托测试，编排本身无覆盖。它内部的流程分支与
``chat`` 的 flow 路由是一份近乎逐行相同的拷贝，重构前先把行为钉住。
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_core.models.agent import AgentStatus
from miles_portal.tenant.agents.schemas.agent import ChatRequest
from miles_portal.tenant.agents.services.agent import chat_entry as entry_mod
from miles_portal.tenant.agents.services.agent.chat_entry import AgentChatEntryMixin

CHILD_ID = uuid4()


class _Hooks:
    def __init__(self, db, tenant_id) -> None:  # noqa: ARG002
        pass


class _FlowRepo:
    def __init__(self, *, flow=None, version=None) -> None:
        self._flow = flow
        self._version = version
        self.get_by_id_calls: list = []
        self.version_calls: list = []

    async def get_by_id(self, flow_id):  # noqa: ANN001
        self.get_by_id_calls.append(flow_id)
        return self._flow

    async def get_version(self, flow_id, n):  # noqa: ANN001, ARG002
        self.version_calls.append(n)
        return self._version


class _Entry(SimpleNamespace):
    """最小工位替身：承载真实 ``chat_as_child``，外部依赖走 fake。"""

    async def get_agent_or_raise(self, child_id):  # noqa: ANN001, ARG002
        return self.child

    async def flow_run_context(self, agent, *, agent_id, inputs, kb_ids, media):  # noqa: ANN001, ARG002
        self.flow_inputs = inputs
        self.flow_ctx_args = (agent_id, kb_ids, media)
        return {"inputs": inputs}

    async def rag_chat(self, agent, body, kb_ids, top_k, agent_id, hooks):  # noqa: ANN001, ARG002
        self.rag_args = (kb_ids, top_k, agent_id)
        return self.rag_response


def _child(**overrides):
    base = {
        "id": CHILD_ID,
        "status": AgentStatus.ENABLED,
        "published_flow_id": None,
        "knowledge_bases": [],
        "config": {},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _entry(*, child=None, flow_repo=None):
    entry = _Entry(
        child=child or _child(),
        db=object(),
        ctx=SimpleNamespace(tenant_id=uuid4()),
    )
    entry.flow_repo = flow_repo or _FlowRepo()
    entry.flow_inputs = None
    entry.flow_ctx_args = None
    entry.rag_args = None
    entry.rag_response = SimpleNamespace(answer="rag-answer", steps=[])
    # 绑定真实的流程执行，让 chat_as_child 的编排逻辑被真实执行
    entry._run_published_flow = AgentChatEntryMixin._run_published_flow.__get__(entry, type(entry))
    return entry


def _bind(entry):
    return AgentChatEntryMixin.chat_as_child.__get__(entry, type(entry))


def _runtime(monkeypatch, output="flow-out", steps=None):
    class _Runtime:
        async def run(self, graph, ctx):  # noqa: ANN001, ARG002
            return SimpleNamespace(output=output, steps=steps or [{"n": 1}])

    monkeypatch.setattr(entry_mod, "get_flow_runtime", lambda: _Runtime())


def _flow_entry(*, flow_id=None, version=1, kb_ids=()):
    """绑定了已发布流程的工位；``version=0`` 表示无已发布版本。"""
    flow_id = flow_id or uuid4()
    return _entry(
        child=_child(published_flow_id=flow_id, knowledge_bases=[SimpleNamespace(id=k) for k in kb_ids]),
        flow_repo=_FlowRepo(
            flow=SimpleNamespace(id=flow_id, current_version=version),
            version=SimpleNamespace(graph_json={}) if version > 0 else None,
        ),
    )


@pytest.fixture(autouse=True)
def _patch_hooks(monkeypatch):
    monkeypatch.setattr(entry_mod, "HookRunner", _Hooks)


# --- 前置校验 ---------------------------------------------------------------


async def test_disabled_child_is_rejected():
    entry = _entry(child=_child(status=AgentStatus.DISABLED))
    with pytest.raises(BadRequestError, match="子智能体已禁用"):
        await _bind(entry)(CHILD_ID, ChatRequest(query="q"))


# --- 流程路由 ---------------------------------------------------------------


async def test_published_flow_runs_and_skips_rag(monkeypatch):
    _runtime(monkeypatch)
    entry = _flow_entry()

    resp = await _bind(entry)(CHILD_ID, ChatRequest(query="q", inputs={"k": "v"}))

    assert resp.answer == "flow-out"
    assert resp.steps == [{"n": 1}]
    assert entry.flow_inputs == {"query": "q", "k": "v"}
    assert entry.rag_args is None


async def test_flow_ctx_uses_child_scope(monkeypatch):
    _runtime(monkeypatch)
    kb = uuid4()
    entry = _flow_entry(kb_ids=[kb])
    media = [{"attachment_id": uuid4()}]

    await _bind(entry)(CHILD_ID, ChatRequest(query="q", media=media))

    agent_id, kb_ids, got_media = entry.flow_ctx_args
    assert agent_id == CHILD_ID
    assert kb_ids == [str(kb)]
    assert [m.attachment_id for m in got_media] == [media[0]["attachment_id"]]


async def test_blank_query_with_media_uses_placeholder(monkeypatch):
    _runtime(monkeypatch)
    entry = _flow_entry()

    await _bind(entry)(CHILD_ID, ChatRequest(query="   ", media=[{"attachment_id": uuid4()}]))

    assert entry.flow_inputs["query"] == "请根据附图回答。"


async def test_blank_query_without_media_keeps_blank(monkeypatch):
    """占位符只补「有媒体」的场景；无媒体时原样透传。

    ``ChatRequest`` 的校验禁止 query 与 media 同时为空，故此处绕过校验直接构造。
    """
    _runtime(monkeypatch)
    entry = _flow_entry()

    await _bind(entry)(CHILD_ID, ChatRequest.model_construct(query="   "))

    assert entry.flow_inputs["query"] == "   "


@pytest.mark.parametrize(
    ("flow", "version"),
    [
        (None, None),  # 流程已被删除
        (SimpleNamespace(id=uuid4(), current_version=1), None),  # 版本行缺失
    ],
    ids=["flow-missing", "version-row-missing"],
)
async def test_flow_fallbacks_go_to_rag(flow, version):
    entry = _entry(child=_child(published_flow_id=uuid4()), flow_repo=_FlowRepo(flow=flow, version=version))

    resp = await _bind(entry)(CHILD_ID, ChatRequest(query="q"))

    assert resp.answer == "rag-answer"
    assert entry.flow_inputs is None
    assert entry.rag_args is not None


async def test_no_published_version_short_circuits_before_version_lookup():
    """``current_version == 0`` 表示尚无已发布版本：直接兜底，不再查版本行。"""
    flow_id = uuid4()
    repo = _FlowRepo(
        flow=SimpleNamespace(id=flow_id, current_version=0),
        version=SimpleNamespace(graph_json={}),  # 即便能查到版本也不该用
    )
    entry = _entry(child=_child(published_flow_id=flow_id), flow_repo=repo)

    resp = await _bind(entry)(CHILD_ID, ChatRequest(query="q"))

    assert resp.answer == "rag-answer"
    assert repo.version_calls == []


# --- RAG 路由 ---------------------------------------------------------------


async def test_no_published_flow_skips_lookup_and_uses_child_defaults():
    kb = uuid4()
    entry = _entry(child=_child(knowledge_bases=[SimpleNamespace(id=kb)]))
    repo = entry.flow_repo

    await _bind(entry)(CHILD_ID, ChatRequest(query="q"))

    assert repo.get_by_id_calls == []  # 未绑定流程时不做无谓查询
    assert entry.rag_args == ([str(kb)], 5, CHILD_ID)


async def test_top_k_read_from_child_config():
    entry = _entry(child=_child(config={"top_k": 9}))

    await _bind(entry)(CHILD_ID, ChatRequest(query="q"))

    assert entry.rag_args[1] == 9
