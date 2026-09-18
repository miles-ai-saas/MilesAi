"""A2A 对外暴露的 HTTP 面：按智能体的 Card 发现端点、JSON-RPC 调用端点、根路径别名。

服务层逻辑已在 ``tests/tenant/a2a/test_a2a_server_card.py`` 覆盖；本文件只锁定路由
装配、状态码与响应形态（Card 用 A2A 原始 JSON、调用用 JSON-RPC 信封，均不套
``{code,message,data}`` 平台信封，否则外部 A2A 客户端解析不了）。
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from miles_common.exceptions import NotFoundError
from miles_core.deps import get_db
from miles_core.tenant import TenantContext
from miles_openapi.views import a2a_server as view_mod
from miles_portal.tenant.a2a.server import agent_card_well_known_path
from miles_portal.tenant.agents.deps_api_auth import require_agent_api_key

AGENT_ID = uuid4()


@pytest.fixture
def as_a2a(api_app):
    """装配 A2A 公开面测试：X-API-Key 鉴权替换为固定租户上下文，并清空 DB 替身。"""
    ctx = TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="a2a-peer",
        is_superuser=False,
        permissions=frozenset({"agent:read"}),
        auth_via="api_key",
    )

    async def override_key() -> TenantContext:
        return ctx

    async def override_db():  # noqa: ANN202
        yield object()

    api_app.dependency_overrides[require_agent_api_key] = override_key
    api_app.dependency_overrides[get_db] = override_db
    return api_app


CARD_PATH = f"/api/v1/open/a2a/agents/{AGENT_ID}/.well-known/agent-card.json"
RPC_PATH = f"/api/v1/open/a2a/agents/{AGENT_ID}"


@pytest.mark.asyncio
async def test_agent_card_endpoint_returns_raw_agent_card(as_a2a, api_client, monkeypatch):
    card = {"name": "客服助手", "skills": [], "supportedInterfaces": []}
    seen: dict = {}

    async def fake_build(_db, _agent_id, *, base_url):  # noqa: ANN001
        seen["base_url"] = base_url
        return card

    monkeypatch.setattr(view_mod, "build_agent_card_by_id", fake_build)

    resp = await api_client.get(CARD_PATH)

    assert resp.status_code == 200
    assert resp.json() == card
    # base_url 由请求推导，多环境无需新增配置项
    assert seen["base_url"].startswith("http://test")


@pytest.mark.asyncio
async def test_agent_card_endpoint_hides_unpublished_agent(as_a2a, api_client, monkeypatch):
    async def raise_not_found(*_args, **_kwargs):
        raise NotFoundError("A2A Server 不存在或未发布")

    monkeypatch.setattr(view_mod, "build_agent_card_by_id", raise_not_found)

    resp = await api_client.get(CARD_PATH)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rpc_endpoint_returns_jsonrpc_envelope(as_a2a, api_client, monkeypatch):
    envelope = {"jsonrpc": "2.0", "id": "1", "result": {"parts": [{"type": "text", "text": "ok"}]}}

    async def fake_rpc(_db, _ctx, _agent_id, payload):  # noqa: ANN001
        assert payload["method"] == "message/send"
        return envelope

    monkeypatch.setattr(view_mod, "handle_a2a_rpc", fake_rpc)

    resp = await api_client.post(
        RPC_PATH,
        json={"jsonrpc": "2.0", "id": "1", "method": "message/send", "params": {}},
    )

    assert resp.status_code == 200
    assert resp.json() == envelope


@pytest.mark.asyncio
async def test_rpc_endpoint_reports_parse_error_as_jsonrpc(as_a2a, api_client):
    resp = await api_client.post(RPC_PATH, content=b"{not json", headers={"Content-Type": "application/json"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["error"]["code"] == -32700


@pytest.mark.asyncio
async def test_well_known_root_redirects_to_unique_published_agent(as_a2a, api_client, monkeypatch):
    async def fake_default(_db):  # noqa: ANN001
        return AGENT_ID

    monkeypatch.setattr(view_mod, "resolve_default_published_agent_id", fake_default)

    resp = await api_client.get("/.well-known/agent-card.json")

    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == agent_card_well_known_path(AGENT_ID)


@pytest.mark.asyncio
async def test_well_known_root_404_when_ambiguous_or_absent(as_a2a, api_client, monkeypatch):
    async def fake_none(_db):  # noqa: ANN001
        return None

    monkeypatch.setattr(view_mod, "resolve_default_published_agent_id", fake_none)

    resp = await api_client.get("/.well-known/agent-card.json")
    assert resp.status_code == 404
