"""A2A 对外暴露的 HTTP 面：按智能体的 Card 发现端点、JSON-RPC 调用端点、根路径别名。

服务层逻辑已在 ``tests/tenant/a2a/test_a2a_server_card.py`` 覆盖；本文件只锁定路由
装配、状态码与响应形态（Card 用 A2A 原始 JSON、调用用 JSON-RPC 信封，均不套
``{code,message,data}`` 平台信封，否则外部 A2A 客户端解析不了）。
"""

from __future__ import annotations

import json
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
    """装配 A2A 公开面测试：X-API-Key 鉴权替换为固定租户上下文，并清空 DB 替身。

    ``api_key_id`` 必须非空：生产里 X-API-Key 通道一定会带上凭证行 id（见
    ``deps_api_auth.ctx_from_api_key``）。若默认成 ``None``，限流按 Key 维度永远不生效，
    测试会把「限流不生效」写成默认态，掩盖真实接线缺陷。
    """
    ctx = TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="a2a-peer",
        is_superuser=False,
        permissions=frozenset({"agent:read"}),
        auth_via="api_key",
        api_key_id=uuid4(),
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
ARTIFACT_PATH = "/api/v1/open/a2a/agents/{}/tasks/{}/artifacts/{}"


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

    async def fake_rpc(_db, _ctx, _agent_id, payload, *, base_url):  # noqa: ANN001
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
async def test_rpc_endpoint_passes_request_base_url(as_a2a, api_client, monkeypatch):
    """Task 产物的下载 URI 必须是绝对地址，故服务层需要请求推导出的 base_url。"""
    seen: dict = {}

    async def fake_rpc(_db, _ctx, _agent_id, payload, *, base_url):  # noqa: ANN001
        seen["base_url"] = base_url
        return {"jsonrpc": "2.0", "id": "1", "result": {}}

    monkeypatch.setattr(view_mod, "handle_a2a_rpc", fake_rpc)

    resp = await api_client.post(RPC_PATH, json={"jsonrpc": "2.0", "id": "1", "method": "tasks/get", "params": {}})

    assert resp.status_code == 200
    assert seen["base_url"].startswith("http://test")


@pytest.mark.asyncio
async def test_task_artifact_endpoint_streams_bytes(as_a2a, api_client, monkeypatch):
    task_id, attachment_id = uuid4(), uuid4()

    async def fake_read(_db, _ctx, _agent_id, _task_id, _attachment_id):  # noqa: ANN001
        return b"PNGDATA", "image/png", "a.png"

    monkeypatch.setattr(view_mod, "read_task_artifact", fake_read)

    resp = await api_client.get(ARTIFACT_PATH.format(AGENT_ID, task_id, attachment_id))

    assert resp.status_code == 200
    assert resp.content == b"PNGDATA"
    assert resp.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_task_artifact_endpoint_404_for_foreign_task(as_a2a, api_client, monkeypatch):
    async def fake_read(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise NotFoundError("任务不存在")

    monkeypatch.setattr(view_mod, "read_task_artifact", fake_read)

    resp = await api_client.get(ARTIFACT_PATH.format(AGENT_ID, uuid4(), uuid4()))
    assert resp.status_code == 404


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


@pytest.mark.asyncio
async def test_stream_method_returns_event_stream(as_a2a, api_client, monkeypatch):
    """message/stream 走 SSE：同一端点按 method 分流，响应体逐帧为 JSON-RPC 信封。"""
    seen: dict = {}

    async def fake_stream(_db, _ctx, _agent_id, payload):  # noqa: ANN001
        seen["method"] = payload["method"]
        seen["agent_id"] = _agent_id

        async def frames():
            yield 'data: {"jsonrpc": "2.0", "id": 1, "result": {"kind": "task"}}\n\n'
            yield 'data: {"jsonrpc": "2.0", "id": 1, "result": {"kind": "status-update", "final": true}}\n\n'

        return frames()

    monkeypatch.setattr(view_mod, "open_a2a_stream", fake_stream)

    resp = await api_client.post(RPC_PATH, json={"jsonrpc": "2.0", "id": 1, "method": "message/stream", "params": {}})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    data_lines = [line for line in resp.text.splitlines() if line.startswith("data: ")]
    assert len(data_lines) == 2
    assert json.loads(data_lines[0][len("data: ") :])["result"]["kind"] == "task"
    assert seen["method"] == "message/stream"
    assert seen["agent_id"] == AGENT_ID


@pytest.mark.asyncio
async def test_stream_preflight_error_keeps_json_content_type(as_a2a, api_client, monkeypatch):
    """前置失败不进 SSE：错误以普通 JSON + JSON-RPC 信封返回，对端才好报错。"""

    async def fake_stream(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "A2A Server 不存在或未发布"}}

    monkeypatch.setattr(view_mod, "open_a2a_stream", fake_stream)

    resp = await api_client.post(RPC_PATH, json={"jsonrpc": "2.0", "id": 1, "method": "message/stream", "params": {}})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json()["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_resubscribe_routes_to_sse_stream(as_a2a, api_client, monkeypatch):
    """tasks/resubscribe 与 message/stream 共用端点，按 method 分流为 SSE。"""
    seen: dict = {}

    async def fake_subscribe(_db, _ctx, _agent_id, payload, *, base_url):  # noqa: ANN001
        seen["method"] = payload["method"]
        seen["base_url"] = base_url

        async def frames():  # noqa: ANN202
            yield 'data: {"jsonrpc": "2.0", "id": 1, "result": {"kind": "task"}}\n\n'
            yield ": ping\n\n"
            yield 'data: {"jsonrpc": "2.0", "id": 1, "result": {"kind": "status-update", "final": true}}\n\n'

        return frames()

    monkeypatch.setattr(view_mod, "open_task_subscription", fake_subscribe)

    resp = await api_client.post(
        RPC_PATH,
        json={"jsonrpc": "2.0", "id": 1, "method": "tasks/resubscribe", "params": {"id": str(uuid4())}},
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    data_lines = [line for line in resp.text.splitlines() if line.startswith("data: ")]
    assert len(data_lines) == 2
    assert json.loads(data_lines[-1][len("data: ") :])["result"]["final"] is True
    assert seen["method"] == "tasks/resubscribe"
    # 产物下载地址是绝对地址，故服务层需要请求推导出的 base_url
    assert seen["base_url"].startswith("http://test")


@pytest.mark.asyncio
async def test_resubscribe_preflight_error_keeps_json_content_type(as_a2a, api_client, monkeypatch):
    """前置失败（任务不存在 / 不属于该智能体 / 合成 id）不进 SSE，仍回 JSON-RPC 信封。"""

    async def fake_subscribe(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32001, "message": "生成任务不存在"}}

    monkeypatch.setattr(view_mod, "open_task_subscription", fake_subscribe)

    resp = await api_client.post(
        RPC_PATH,
        json={"jsonrpc": "2.0", "id": 1, "method": "tasks/resubscribe", "params": {"id": str(uuid4())}},
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json()["error"]["code"] == -32001


@pytest.mark.asyncio
async def test_resubscribe_rate_limited_before_sse(as_a2a, api_client, monkeypatch):
    """订阅可能开 30 分钟，超限更要在开流前拦下（否则 429 无处安放）。"""
    from miles_core.risk.enforce import RateLimitHit

    seen: dict = {}

    async def fake_limit(*_args, **kwargs):  # noqa: ANN002, ANN003
        seen["path"] = kwargs["path"]
        return RateLimitHit(rule_id=uuid4(), limit_per_minute=5, retry_after_seconds=3)

    def fail_subscribe(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("超限时不应进入订阅生成器")

    monkeypatch.setattr(view_mod, "check_a2a_rate_limit", fake_limit)
    monkeypatch.setattr(view_mod, "open_task_subscription", fail_subscribe)

    resp = await api_client.post(
        RPC_PATH,
        json={"jsonrpc": "2.0", "id": 1, "method": "tasks/resubscribe", "params": {"id": str(uuid4())}},
    )

    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "3"
    assert resp.json()["error"]["code"] == -32000
    assert seen["path"] == RPC_PATH


@pytest.mark.asyncio
async def test_rpc_endpoint_rate_limited_returns_429_with_jsonrpc_body(as_a2a, api_client, monkeypatch):
    """超限必须让对端能退避：429 + Retry-After，且正文仍是它读得懂的 JSON-RPC 信封。"""
    from miles_core.risk.enforce import RateLimitHit

    seen: dict = {}

    async def fake_limit(*_args, **kwargs):  # noqa: ANN002, ANN003
        seen["path"] = kwargs["path"]
        return RateLimitHit(rule_id=uuid4(), limit_per_minute=5, retry_after_seconds=7)

    monkeypatch.setattr(view_mod, "check_a2a_rate_limit", fake_limit)

    resp = await api_client.post(RPC_PATH, json={"jsonrpc": "2.0", "id": "9", "method": "message/send", "params": {}})

    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "7"
    body = resp.json()
    assert body["jsonrpc"] == "2.0" and body["id"] == "9"
    assert body["error"]["code"] == -32000
    assert body["error"]["data"]["retryAfterSeconds"] == 7
    # 风控规则按 path_pattern 匹配 path：若视图传了 base_url / 带查询串 / 漏了 /api/v1 前缀，
    # 限流会静默失效且状态码断言看不出 —— 故锁定实际入参。
    assert seen["path"] == RPC_PATH


@pytest.mark.asyncio
async def test_stream_method_rate_limited_before_sse(as_a2a, api_client, monkeypatch):
    """流式请求超限必须在开流前拦下：一旦响应头写成 text/event-stream，429 就塞不进去了。"""
    from miles_core.risk.enforce import RateLimitHit

    seen: dict = {}

    async def fake_limit(*_args, **kwargs):  # noqa: ANN002, ANN003
        seen["path"] = kwargs["path"]
        return RateLimitHit(rule_id=uuid4(), limit_per_minute=5, retry_after_seconds=3)

    def fail_stream(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("超限时不应进入 SSE 生成器")

    monkeypatch.setattr(view_mod, "check_a2a_rate_limit", fake_limit)
    monkeypatch.setattr(view_mod, "open_a2a_stream", fail_stream)

    resp = await api_client.post(RPC_PATH, json={"jsonrpc": "2.0", "id": 1, "method": "message/stream", "params": {}})

    assert resp.status_code == 429
    assert resp.headers["content-type"].startswith("application/json")
    assert seen["path"] == RPC_PATH


@pytest.mark.asyncio
async def test_artifact_endpoint_rate_limited_uses_platform_envelope(as_a2a, api_client, monkeypatch):
    """产物下载是普通 HTTP 下载而非 JSON-RPC，超限形状与中间件 429 一致（平台信封）。"""
    from miles_core.risk.enforce import RateLimitHit

    task_id, attachment_id = uuid4(), uuid4()
    path = ARTIFACT_PATH.format(AGENT_ID, task_id, attachment_id)
    seen: dict = {}

    async def fake_limit(*_args, **kwargs):  # noqa: ANN002, ANN003
        seen["path"] = kwargs["path"]
        return RateLimitHit(rule_id=uuid4(), limit_per_minute=5, retry_after_seconds=4)

    monkeypatch.setattr(view_mod, "check_a2a_rate_limit", fake_limit)

    resp = await api_client.get(path)

    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "4"
    assert resp.json()["code"] == 429
    assert resp.json()["message"] == "请求过于频繁，请稍后再试"
    assert seen["path"] == path
