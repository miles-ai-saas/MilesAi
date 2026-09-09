"""chat_as_child_simple 委托 chat_as_child 并构造子任务 ChatRequest（L3 deepagents 契约用）。"""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

from app.tenant.agents.schemas.agent import ChatRequest, ChatResponse


def _run(coro):
    return asyncio.run(coro)


class _ChildEntry(SimpleNamespace):
    """最小替身：仅承载被委托的 chat_as_child，记录入参。"""

    async def chat_as_child(self, child_id, body: ChatRequest) -> ChatResponse:
        self.calls.append((child_id, body))
        return ChatResponse(answer="child-ok")


def test_chat_as_child_simple_builds_chat_request():
    from app.tenant.agents.services.agent.chat_entry import AgentChatEntryMixin

    entry = _ChildEntry()
    entry.calls = []
    bound = AgentChatEntryMixin.chat_as_child_simple.__get__(entry, type(entry))
    child_id = uuid4()
    resp = _run(bound(child_id, query="q", inputs={"k": "v"}))

    assert resp.answer == "child-ok"
    (got_child, body) = entry.calls[0]
    assert got_child == child_id
    assert isinstance(body, ChatRequest)
    assert body.query == "q"
    assert body.inputs == {"k": "v"}


def test_chat_as_child_simple_defaults_inputs_empty():
    from app.tenant.agents.services.agent.chat_entry import AgentChatEntryMixin

    entry = _ChildEntry()
    entry.calls = []
    bound = AgentChatEntryMixin.chat_as_child_simple.__get__(entry, type(entry))
    _run(bound(uuid4(), query="hi"))
    (_child, body) = entry.calls[0]
    assert body.inputs == {}
