"""Hook Event v1 与执行器行为。"""

from uuid import uuid4

import pytest

from app.tenant.hooks.events import apply_modify, build_event_envelope, parse_hook_response
from app.tenant.hooks.models import HookScope, HookTrigger


def test_build_event_envelope():
    tid = uuid4()
    hid = uuid4()
    env = build_event_envelope(
        tenant_id=tid,
        trace_id="trace-1",
        trigger=HookTrigger.BEFORE_CALL,
        scope=HookScope.AGENT,
        target_id=uuid4(),
        hook_id=hid,
        hook_name="audit",
        payload={"query": "hi"},
    )
    assert env["schema_version"] == "1"
    assert env["tenant_id"] == str(tid)
    assert env["payload"]["query"] == "hi"
    assert env["hook"]["name"] == "audit"


def test_parse_block_and_modify():
    parsed = parse_hook_response(
        {"schema_version": "1", "action": "block", "message": "denied"}
    )
    assert parsed.action == "block"
    assert parsed.message == "denied"

    parsed2 = parse_hook_response(
        {"schema_version": "1", "action": "modify", "modify": {"query": "new"}}
    )
    assert parsed2.modify["query"] == "new"


def test_apply_modify_allowlist():
    payload = {"query": "old", "secret": "x"}
    out = apply_modify(
        payload,
        HookTrigger.BEFORE_CALL,
        {"query": "new", "secret": "y"},
    )
    assert out["query"] == "new"
    assert out["secret"] == "x"
