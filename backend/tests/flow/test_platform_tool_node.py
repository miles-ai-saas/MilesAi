"""画布 PlatformTool 节点。"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.flow_runtime.nodes.tool_nodes import _build_invoke_params, platform_tool
from app.flow_runtime.types import RunContext


class _FakeDbSession:
    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *args):
        return None


def test_build_invoke_params_kb_default():
    ctx = RunContext(tenant_id=str(uuid4()), kb_ids=["kb-1", "kb-2"])
    params = _build_invoke_params(
        {"tool_slug": "knowledge_search", "merge_input": True},
        {"query": "hello"},
        ctx,
    )
    assert params["query"] == "hello"
    assert params["kb_id"] == "kb-1"


@pytest.mark.asyncio
async def test_platform_tool_invoke(monkeypatch):
    captured: dict = {}

    async def _invoke(db, tenant_ctx, slug, params, **kwargs):
        captured["slug"] = slug
        captured["params"] = params
        captured["agent_id"] = kwargs.get("agent_id")
        return {"ok": True}

    monkeypatch.setattr(
        "app.flow_runtime.nodes.tool_nodes.invoke_tool_with_context",
        _invoke,
    )
    monkeypatch.setattr(
        "app.flow_runtime.nodes.tool_nodes.AsyncSessionLocal",
        lambda: _FakeDbSession(),
    )

    ctx = RunContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        agent_id=str(uuid4()),
        agent_config={"skill_package_id": str(uuid4())},
        kb_ids=["kb-a"],
    )
    out = await platform_tool(
        {"tool_slug": "skill_read_reference", "params": {"path": "references/x.md"}},
        {"input": "ignored"},
        ctx,
    )
    assert out["tool_slug"] == "skill_read_reference"
    assert captured["slug"] == "skill_read_reference"
    assert captured["params"]["path"] == "references/x.md"
    assert captured["agent_id"] is not None
