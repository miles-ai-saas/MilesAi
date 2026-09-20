"""A2A 调用审计：独立会话写入、不记正文、失败不惊动业务。"""

from __future__ import annotations

from uuid import uuid4

import pytest

from miles_core.tenant import TenantContext
from miles_portal.tenant.a2a import server as server_mod
from miles_portal.tenant.a2a.services import audit as audit_mod

AGENT_ID = uuid4()


def _ctx() -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="a2a-peer",
        is_superuser=False,
        permissions=frozenset({"agent:read"}),
        auth_via="api_key",
        api_key_id=uuid4(),
    )


class _FakeSession:
    """记录 ``commit`` / ``closed`` 的最小会话替身。"""

    def __init__(self) -> None:
        self.committed = 0
        self.closed = 0

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        self.closed += 1
        return False

    async def commit(self) -> None:
        self.committed += 1


@pytest.mark.asyncio
async def test_audit_uses_own_session_and_commits(monkeypatch):  # noqa: ANN001
    """审计必须自开会话并 commit：复用请求作用域会话时，业务失败回滚会连带吞掉留痕。"""
    session = _FakeSession()
    written: list[dict] = []
    monkeypatch.setattr(audit_mod, "AsyncSessionLocal", lambda: session)

    async def fake_write(_db, ctx, **kwargs):  # noqa: ANN001, ANN003
        written.append({"ctx": ctx, **kwargs})

    monkeypatch.setattr(audit_mod, "write_tenant_audit_log", fake_write)
    ctx = _ctx()

    await audit_mod.write_a2a_audit(
        ctx=ctx, agent_id=AGENT_ID, action=server_mod.AUDIT_ACTION_MESSAGE_SEND, outcome=server_mod.AUDIT_OUTCOME_OK, detail={"method": "message/send"}
    )

    assert session.closed == 1
    assert session.committed == 1
    assert len(written) == 1
    assert written[0]["action"] == "a2a.message.send"
    assert written[0]["resource_type"] == "agent"
    assert written[0]["resource_id"] == str(AGENT_ID)
    assert written[0]["detail"]["outcome"] == "ok"
    assert written[0]["detail"]["apiKeyId"] == str(ctx.api_key_id)
    assert written[0]["detail"]["method"] == "message/send"


@pytest.mark.asyncio
async def test_audit_failure_never_breaks_caller(monkeypatch):  # noqa: ANN001
    """审计是旁路：写不进去只能记日志，不得让业务调用失败。"""

    def boom() -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr(audit_mod, "AsyncSessionLocal", boom)

    await audit_mod.write_a2a_audit(ctx=_ctx(), agent_id=AGENT_ID, action=server_mod.AUDIT_ACTION_TASKS_GET, outcome=server_mod.AUDIT_OUTCOME_OK)


def test_a2a_audit_actions_are_registered_in_audit_meta():
    """写入的 action 必须登记进审计页筛选列表，否则租户在下拉里筛不到自己的 A2A 调用。"""
    from miles_portal.tenant.audit_log.meta import ACTION_FILTER_OPTIONS

    registered = {value for value, _, _ in ACTION_FILTER_OPTIONS}
    expected = {
        server_mod.AUDIT_ACTION_MESSAGE_SEND,
        server_mod.AUDIT_ACTION_MESSAGE_STREAM,
        server_mod.AUDIT_ACTION_TASKS_GET,
        server_mod.AUDIT_ACTION_TASKS_CANCEL,
        server_mod.AUDIT_ACTION_ARTIFACT_DOWNLOAD,
    }
    assert expected <= registered, f"未登记：{sorted(expected - registered)}"


def test_audit_actions_are_namespaced():
    """动作名统一 ``a2a.`` 前缀：租户审计页按动作筛选时才聚得起来。"""
    assert all(
        action.startswith("a2a.")
        for action in (
            server_mod.AUDIT_ACTION_MESSAGE_SEND,
            server_mod.AUDIT_ACTION_MESSAGE_STREAM,
            server_mod.AUDIT_ACTION_TASKS_GET,
            server_mod.AUDIT_ACTION_TASKS_CANCEL,
            server_mod.AUDIT_ACTION_ARTIFACT_DOWNLOAD,
        )
    )
