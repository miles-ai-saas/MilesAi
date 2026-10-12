"""内置 list_attachments：资源范围护栏与分页夹取。"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_common.schema import PageResult
from miles_portal.tenant.tools.services import list_attachments as mod


def test_resolve_defaults_to_agent():
    agent_id = uuid4()
    rt, rid, purpose = mod.resolve_attachment_list_scope({}, agent_id=agent_id)
    assert rt == "agent"
    assert rid == agent_id
    assert purpose is None


def test_resolve_explicit_resource():
    rid = uuid4()
    rt, out_rid, purpose = mod.resolve_attachment_list_scope(
        {"resource_type": "flow", "resource_id": str(rid), "purpose": "flow"},
        agent_id=None,
    )
    assert rt == "flow"
    assert out_rid == rid
    assert purpose == "flow"


def test_resolve_requires_pair():
    with pytest.raises(BadRequestError, match="成对"):
        mod.resolve_attachment_list_scope({"resource_type": "agent"}, agent_id=None)


def test_resolve_requires_scope():
    with pytest.raises(BadRequestError, match="资源范围"):
        mod.resolve_attachment_list_scope({}, agent_id=None)


def test_resolve_rejects_bad_purpose():
    with pytest.raises(BadRequestError, match="purpose"):
        mod.resolve_attachment_list_scope({"purpose": "evil"}, agent_id=uuid4())


@pytest.mark.asyncio
async def test_list_scoped_attachments_delegates(monkeypatch):
    agent_id = uuid4()
    att_id = uuid4()
    now = datetime.now(UTC)
    page = PageResult(
        items=[
            SimpleNamespace(
                id=att_id,
                filename="a.png",
                mime_type="image/png",
                file_size=12,
                purpose="chat",
                resource_type="agent",
                resource_id=agent_id,
                created_at=now,
            )
        ],
        total=1,
        page=1,
        size=10,
    )

    svc = SimpleNamespace(list_attachments=AsyncMock(return_value=page))

    class _FakeService:
        def __init__(self, db, ctx):
            self.db = db
            self.ctx = ctx

        list_attachments = svc.list_attachments

    monkeypatch.setattr(mod, "AttachmentService", _FakeService)

    out = await mod.list_scoped_attachments(
        SimpleNamespace(),
        SimpleNamespace(tenant_id=uuid4()),
        {"purpose": "chat", "size": 99},
        agent_id=agent_id,
    )

    assert out["total"] == 1
    assert out["items"][0]["id"] == str(att_id)
    assert out["scope"] == {
        "resource_type": "agent",
        "resource_id": str(agent_id),
        "purpose": "chat",
    }
    call_args = svc.list_attachments.await_args
    params = call_args.args[0]
    assert params.size == 20  # 夹取上限
    assert call_args.kwargs["purpose"] == "chat"
    assert call_args.kwargs["resource_type"] == "agent"
    assert call_args.kwargs["resource_id"] == agent_id
