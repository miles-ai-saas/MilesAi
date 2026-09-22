"""``AgentChatSessionService.persist_turn`` 特征化测试（重构前锁定行为）。

核心不变量：同一回合写入的 user / assistant 两条消息，其
``session_id``/``tenant_id``/``agent_id`` 必须完全一致，且与所属会话行一致。
任一处漂移都会让助手回复落到别的会话或租户下（消息按 session_id 聚合查询）。
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from miles_core.models.agent.chat_session import AgentChatMessage, AgentChatSession
from miles_core.tenant import TenantContext
from miles_portal.tenant.agents.services import chat_sessions as cs_mod


def _ctx(tenant_id, *, user_id=None) -> TenantContext:
    return TenantContext(
        user_id=user_id or uuid4(),
        tenant_id=tenant_id,
        username="t",
        is_superuser=False,
        permissions=frozenset(),
    )


def _body(*, conversation_id="conv-1", media=None) -> SimpleNamespace:
    return SimpleNamespace(conversation_id=conversation_id, media=media or [])


def _response(*, answer="回答", steps=None) -> SimpleNamespace:
    return SimpleNamespace(answer=answer, steps=steps, artifacts=None, generative_jobs=None)


class _FakeDb:
    def __init__(self, session_row=None) -> None:
        self._session_row = session_row
        self.added: list = []
        self.flushes = 0

    async def get(self, model, pk):  # noqa: ANN001
        return self._session_row

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushes += 1


def _svc(db, ctx, *, next_sort=3):  # noqa: ANN001
    svc = cs_mod.AgentChatSessionService(db, ctx)
    calls: list[str] = []

    async def _next_sort_index(session_id):  # noqa: ANN001
        calls.append(session_id)
        return next_sort

    svc._next_sort_index = _next_sort_index
    svc.sort_calls = calls
    return svc


def _messages(db) -> list:
    return [o for o in db.added if isinstance(o, AgentChatMessage)]


def _sessions(db) -> list:
    return [o for o in db.added if isinstance(o, AgentChatSession)]


# --------------------------------------------------------------------------- #
# 早退路径
# --------------------------------------------------------------------------- #


async def test_missing_conversation_id_writes_nothing():  # noqa: ANN001
    ctx = _ctx(uuid4())
    db = _FakeDb()
    svc = _svc(db, ctx)

    await svc.persist_turn(uuid4(), _body(conversation_id="  "), response=_response(), trace_id=None, user_query="你好")

    assert db.added == []
    assert svc.sort_calls == []


async def test_session_owned_by_other_agent_is_ignored():  # noqa: ANN001
    tenant_id = uuid4()
    row = SimpleNamespace(agent_id=uuid4(), tenant_id=tenant_id, title="新对话", updated_at=None)
    db = _FakeDb(session_row=row)
    svc = _svc(db, _ctx(tenant_id))

    await svc.persist_turn(
        uuid4(),  # 与 row.agent_id 不同
        _body(),
        response=_response(),
        trace_id=None,
        user_query="你好",
    )

    assert db.added == []


async def test_session_owned_by_other_tenant_is_ignored():  # noqa: ANN001
    agent_id = uuid4()
    row = SimpleNamespace(agent_id=agent_id, tenant_id=uuid4(), title="新对话", updated_at=None)
    db = _FakeDb(session_row=row)
    svc = _svc(db, _ctx(uuid4()))

    await svc.persist_turn(agent_id, _body(), response=_response(), trace_id=None, user_query="你好")

    assert db.added == []


# --------------------------------------------------------------------------- #
# 新建会话
# --------------------------------------------------------------------------- #


async def test_new_session_row_carries_tenant_agent_and_creator():  # noqa: ANN001
    tenant_id, agent_id, me = uuid4(), uuid4(), uuid4()
    ctx = _ctx(tenant_id, user_id=me)
    db = _FakeDb(session_row=None)
    svc = _svc(db, ctx)

    await svc.persist_turn(agent_id, _body(), response=_response(), trace_id="t1", user_query="第一个问题")

    (session,) = _sessions(db)
    assert session.id == "conv-1"
    assert session.tenant_id == tenant_id
    assert session.agent_id == agent_id
    assert session.created_by == me
    # 新建行初值 "新对话"，随后统一经 _derive_title 推导为本次提问
    assert session.title == "第一个问题"


async def test_title_derived_from_first_user_query():  # noqa: ANN001
    tenant_id, agent_id = uuid4(), uuid4()
    row = SimpleNamespace(agent_id=agent_id, tenant_id=tenant_id, title="新对话", updated_at=None)
    db = _FakeDb(session_row=row)
    svc = _svc(db, _ctx(tenant_id))

    await svc.persist_turn(agent_id, _body(), response=_response(), trace_id=None, user_query="帮我写周报")

    assert row.title == "帮我写周报"


async def test_existing_title_is_not_overwritten():  # noqa: ANN001
    tenant_id, agent_id = uuid4(), uuid4()
    row = SimpleNamespace(agent_id=agent_id, tenant_id=tenant_id, title="旧标题", updated_at=None)
    db = _FakeDb(session_row=row)
    svc = _svc(db, _ctx(tenant_id))

    await svc.persist_turn(agent_id, _body(), response=_response(), trace_id=None, user_query="新问题")

    assert row.title == "旧标题"


# --------------------------------------------------------------------------- #
# 两条消息
# --------------------------------------------------------------------------- #


async def test_two_messages_share_conversation_tenant_and_agent():  # noqa: ANN001
    """核心不变量：user 与 assistant 行的身份三元组必须一致。"""
    tenant_id, agent_id = uuid4(), uuid4()
    db = _FakeDb()
    svc = _svc(db, _ctx(tenant_id))

    await svc.persist_turn(agent_id, _body(), response=_response(), trace_id=None, user_query="你好")

    user_msg, assistant_msg = _messages(db)
    assert user_msg.role == "user"
    assert assistant_msg.role == "assistant"
    for field in ("session_id", "tenant_id", "agent_id"):
        assert getattr(user_msg, field) == getattr(assistant_msg, field), f"{field} 在两条消息间漂移"
    assert user_msg.session_id == "conv-1"
    assert user_msg.tenant_id == tenant_id
    assert user_msg.agent_id == agent_id


async def test_assistant_reply_uses_response_content_and_trace():  # noqa: ANN001
    db = _FakeDb()
    svc = _svc(db, _ctx(uuid4()))

    await svc.persist_turn(uuid4(), _body(), response=_response(answer="最终答复"), trace_id="trace-9", user_query="问")

    assistant_msg = _messages(db)[1]
    assert assistant_msg.content == "最终答复"
    assert assistant_msg.trace_id == "trace-9"
    assert _messages(db)[0].trace_id is None


async def test_no_response_writes_only_user_message():  # noqa: ANN001
    db = _FakeDb()
    svc = _svc(db, _ctx(uuid4()))

    await svc.persist_turn(uuid4(), _body(), response=None, trace_id=None, user_query="只有提问")

    assert [m.role for m in _messages(db)] == ["user"]


async def test_sort_index_increments_between_user_and_assistant():  # noqa: ANN001
    db = _FakeDb()
    svc = _svc(db, _ctx(uuid4()), next_sort=7)

    await svc.persist_turn(uuid4(), _body(), response=_response(), trace_id=None, user_query="你好")

    user_msg, assistant_msg = _messages(db)
    assert user_msg.sort_index == 7
    assert assistant_msg.sort_index == 8
    assert svc.sort_calls == ["conv-1"]


async def test_steps_nulled_when_empty():  # noqa: ANN001
    db = _FakeDb()
    svc = _svc(db, _ctx(uuid4()))

    await svc.persist_turn(uuid4(), _body(), response=_response(steps=[]), trace_id=None, user_query="你好")

    assert _messages(db)[1].steps is None


async def test_media_payload_mapped_from_request():  # noqa: ANN001
    attachment_id = uuid4()
    media = [SimpleNamespace(attachment_id=attachment_id, detail="high")]
    db = _FakeDb()
    svc = _svc(db, _ctx(uuid4()))

    await svc.persist_turn(uuid4(), _body(media=media), response=_response(), trace_id=None, user_query="看图")

    assert _messages(db)[0].media == [{"attachment_id": str(attachment_id), "detail": "high"}]


async def test_new_session_is_flushed_before_messages():  # noqa: ANN001
    """新会话行需先 flush 落库，消息再引用其 id。"""
    db = _FakeDb(session_row=None)
    svc = _svc(db, _ctx(uuid4()))

    await svc.persist_turn(uuid4(), _body(), response=_response(), trace_id=None, user_query="你好")

    assert db.flushes >= 1
    assert len(_sessions(db)) == 1
    assert len(_messages(db)) == 2
