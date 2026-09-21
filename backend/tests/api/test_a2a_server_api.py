"""A2A 对外暴露的 HTTP 面：按智能体的 Card 发现端点、JSON-RPC 调用端点、根路径别名。

服务层逻辑已在 ``tests/tenant/a2a/test_a2a_server_card.py`` 覆盖；本文件只锁定路由
装配、状态码与响应形态（Card 用 A2A 原始 JSON、调用用 JSON-RPC 信封，均不套
``{code,message,data}`` 平台信封，否则外部 A2A 客户端解析不了）。
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError, ForbiddenError, NotFoundError
from miles_core.deps import get_db
from miles_core.models.agent import Agent, AgentStatus, AgentType
from miles_core.tenant import TenantContext
from miles_openapi.views import a2a_server as view_mod
from miles_portal.tenant.a2a.server import A2A_PUBLISH_FLAG, agent_card_well_known_path
from miles_portal.tenant.a2a.services import audit as audit_svc
from miles_portal.tenant.a2a.services import server as a2a_svc
from miles_portal.tenant.a2a.services import subscription as subscription_svc
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
async def test_resubscribe_end_to_end_real_service_through_http(as_a2a, api_client, monkeypatch):
    """唯一把「真实前置校验 + 真实帧编码 + 真实 StreamingResponse」串起来跑的用例。

    上面的路由用例把 ``open_task_subscription`` 整个换掉，服务层用例又把
    ``watch_generative_job`` 换掉：两道缝各自成立，但它们的**组合**从未跑过。这里只换
    watcher 这个 I/O 出口，其余全真，让请求真的经 ASGI 走完一次订阅。
    """
    attachment_id = uuid4()
    job_id = uuid4()
    agent = Agent()
    agent.id = AGENT_ID
    agent.agent_type = AgentType.CUSTOM
    agent.status = AgentStatus.ENABLED
    agent.config = {A2A_PUBLISH_FLAG: True}
    agent.deleted_at = None

    class _Db:
        """最小 DB 替身：服务层只用 ``get``（取智能体）与 ``commit``（结束请求级事务）。"""

        def __init__(self):  # noqa: ANN204
            self.committed = 0

        async def get(self, _model, _id):  # noqa: ANN001
            return agent

        async def commit(self):  # noqa: ANN201
            self.committed += 1

    db = _Db()

    async def override_db():  # noqa: ANN202
        yield db

    as_a2a.dependency_overrides[get_db] = override_db

    def _job(status, **overrides):  # noqa: ANN001, ANN202
        base = dict(
            id=job_id,
            tenant_id=uuid4(),
            status=SimpleNamespace(value=status),
            progress_message=None,
            progress_percent=None,
            result=None,
            params={},
            source_ref_type="agent",
            source_ref_id=AGENT_ID,
        )
        base.update(overrides)
        return SimpleNamespace(**base)

    running = _job("running", progress_message="渲染中", progress_percent=20)
    done = _job(
        "success",
        progress_message="已完成",
        progress_percent=100,
        result={"attachment_id": str(attachment_id), "mime_type": "image/png", "kind": "image"},
    )

    async def _owned(_db, _ctx, _task_id):  # noqa: ANN001
        return running

    async def _watcher(**_kwargs):  # noqa: ANN003
        yield running
        yield None  # 空闲刻度：真实路径要把它变成保活注释帧
        yield done

    recorded: list[dict] = []

    async def _write(**kwargs):  # noqa: ANN003
        recorded.append(kwargs)

    monkeypatch.setattr(a2a_svc, "get_generative_job_for_tenant", _owned)
    monkeypatch.setattr(subscription_svc, "watch_generative_job", _watcher)
    monkeypatch.setattr(subscription_svc, "write_a2a_audit", _write)

    resp = await api_client.post(
        RPC_PATH,
        json={"jsonrpc": "2.0", "id": 7, "method": "tasks/resubscribe", "params": {"id": str(job_id)}},
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    results = [json.loads(line[len("data: ") :])["result"] for line in resp.text.splitlines() if line.startswith("data: ")]
    assert [r["kind"] for r in results] == ["task", "artifact-update", "status-update"]
    # 产物 URI 的 base_url 由请求推导：绝对地址一旦退化成相对路径，对端就取不到产物
    assert results[1]["artifact"]["parts"][0]["file"]["uri"] == f"http://test/api/v1/open/a2a/agents/{AGENT_ID}/tasks/{job_id}/artifacts/{attachment_id}"
    assert results[-1]["final"] is True and results[-1]["status"]["state"] == "completed"
    # 保活注释帧经真实编码路径原样透传（对端与中间代理靠它判断连接还活着）
    assert ": ping" in resp.text
    # 30 分钟的订阅不能陪跑一条请求级连接：进流之前就该结束事务
    assert db.committed == 1

    await audit_svc.drain_pending_audits()
    assert len(recorded) == 1
    assert recorded[0]["detail"]["endedBy"] == "terminal"
    assert recorded[0]["detail"]["taskId"] == str(job_id)


@pytest.mark.asyncio
async def test_tasks_get_foreign_tenant_returns_jsonrpc_not_platform_envelope(as_a2a, api_client, monkeypatch):
    """外租户 id 必须收敛为 HTTP 200 + JSON-RPC ``-32001``，而不是平台信封的 403。

    服务层单测直接 ``await handle_a2a_rpc``，看不到 HTTP 状态码与 Content-Type —— 而本缺陷
    的可观测面恰在两者之间（协议契约要求 HTTP 200 + JSON-RPC 正文）。这里只替换 I/O 出口
    （取任务 = 抛外租户 403、审计 = 记录），其余全真，让请求经 ASGI 走完一次分发。
    """
    agent = Agent()
    agent.id = AGENT_ID
    agent.agent_type = AgentType.CUSTOM
    agent.status = AgentStatus.ENABLED
    agent.config = {A2A_PUBLISH_FLAG: True}
    agent.deleted_at = None

    class _Db:
        """最小 DB 替身：本路径只用到 ``get``（取智能体）。"""

        async def get(self, _model, _id):  # noqa: ANN001
            return agent

        async def commit(self):  # noqa: ANN201
            pass

    async def override_db():  # noqa: ANN202
        yield _Db()

    async def _foreign(_db, _ctx, _job_id):  # noqa: ANN001
        raise ForbiddenError("无权访问该租户资源")

    recorded: list[dict] = []

    async def _write(**kwargs):  # noqa: ANN003
        recorded.append(kwargs)

    as_a2a.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(a2a_svc, "get_generative_job_for_tenant", _foreign)
    monkeypatch.setattr(a2a_svc, "write_a2a_audit", _write)

    resp = await api_client.post(
        RPC_PATH,
        json={"jsonrpc": "2.0", "id": 5, "method": "tasks/get", "params": {"id": str(uuid4())}},
    )

    assert resp.status_code == 200
    # 只保证正文是 JSON（防 SSE 串线把 text/event-stream 写出来）：JSON-RPC 信封与平台信封
    # 都是 ``JSONResponse``，故这条对「403 是否逸出」零判别力，判别交给下面的键集断言。
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 5
    assert body["error"]["code"] == -32001
    # 平台信封是 ``{code, message, data, trace_id}``：键集不等即说明 403 逸出到了全局处理器。
    # 单看 ``trace_id`` 只是单键指纹，且它的判别力从未被 RED 覆盖过。
    assert set(body) == {"jsonrpc", "id", "error"}
    # 探测式调用必须留痕，且错误码不再是兜底路径误标的 -32603
    assert len(recorded) == 1
    assert recorded[0]["outcome"] == "failed"
    assert recorded[0]["detail"]["errorCode"] == -32001
    # 审计 ``detail`` 绝不含正文：键集等值把这条全局约束从「顺带成立」变成可执行断言
    assert set(recorded[0]["detail"]) == {"method", "taskId", "errorCode", "durationMs"}


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


# --- 错误封口：业务异常不得逸出成平台信封 ------------------------------------- #


def _published_agent():  # noqa: ANN202
    """已发布 custom 智能体：`message/send` 的前置门槛要求它。"""
    agent = Agent()
    agent.id = AGENT_ID
    agent.agent_type = AgentType.CUSTOM
    agent.status = AgentStatus.ENABLED
    agent.config = {A2A_PUBLISH_FLAG: True}
    agent.deleted_at = None
    return agent


class _AgentDb:
    """本组用例只用到 ``get``（取智能体）。注意 `load_published_agent` 里是 `await db.get(...)`。"""

    async def get(self, _model, _id):  # noqa: ANN001
        return _published_agent()

    async def commit(self):  # noqa: ANN201
        pass


def _use_agent_db(app):  # noqa: ANN001, ANN202
    """把 `get_db` 覆盖成 `_AgentDb`（`as_a2a` 默认给的是 `object()`）。"""

    async def override_db():  # noqa: ANN202
        yield _AgentDb()

    app.dependency_overrides[get_db] = override_db


@pytest.mark.asyncio
async def test_tasks_cancel_race_returns_jsonrpc_not_platform_envelope(as_a2a, api_client, monkeypatch):
    """E2 的 HTTP 面：`cancel_job` 竞态 `NotFoundError` → HTTP 200 + `-32001`，不是 404 平台信封。

    `tasks/cancel` 不查智能体发布状态，故本用例只需替换「取任务 / 取消 / 审计」三个 I/O 出口。
    修复前该异常逸出到全局 `AppError` 专属处理器，回 **404 平台信封**（审计误记 `-32603`）；
    HTTP 500 只留给非 `AppError`。
    """
    job = SimpleNamespace(
        id=uuid4(),
        status=SimpleNamespace(value="running"),
        params={},
        result=None,
        source_ref_type="agent",
        source_ref_id=AGENT_ID,
    )

    async def _owned(_db, _ctx, _job_id):  # noqa: ANN001
        return job

    class _Raced:
        def __init__(self, _db, _ctx) -> None:
            pass

        async def cancel_job(self, _job_id):  # noqa: ANN001
            raise NotFoundError("生成任务不存在")

    recorded: list[dict] = []

    async def _write(**kwargs):  # noqa: ANN003
        recorded.append(kwargs)

    monkeypatch.setattr(a2a_svc, "get_generative_job_for_tenant", _owned)
    monkeypatch.setattr(a2a_svc, "GenerativeJobService", _Raced)
    monkeypatch.setattr(a2a_svc, "write_a2a_audit", _write)

    resp = await api_client.post(
        RPC_PATH,
        json={"jsonrpc": "2.0", "id": 4, "method": "tasks/cancel", "params": {"id": str(job.id)}},
    )

    assert resp.status_code == 200
    body = resp.json()
    # 键集等值即「没有逸出到全局处理器」：平台信封是 {code,message,data,trace_id}
    assert set(body) == {"jsonrpc", "id", "error"}
    assert body["id"] == 4
    assert body["error"]["code"] == -32001
    assert len(recorded) == 1
    assert recorded[0]["detail"]["errorType"] == "NotFoundError"
    assert recorded[0]["detail"]["errorStatus"] == 404


@pytest.mark.asyncio
async def test_message_send_compliance_block_returns_invalid_params(as_a2a, api_client, monkeypatch):
    """E3 的 HTTP 面：合规拦截（`BadRequestError`）→ HTTP 200 + `-32602`，不是 `-32603`。"""

    async def _blocked(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise BadRequestError("输入内容包含敏感词，已拦截：某词")

    recorded: list[dict] = []

    async def _write(**kwargs):  # noqa: ANN003
        recorded.append(kwargs)

    _use_agent_db(as_a2a)
    monkeypatch.setattr(a2a_svc, "run_published_agent_chat", _blocked)
    monkeypatch.setattr(a2a_svc, "write_a2a_audit", _write)

    resp = await api_client.post(
        RPC_PATH,
        json={
            "jsonrpc": "2.0",
            "id": 6,
            "method": "message/send",
            "params": {"message": {"parts": [{"kind": "text", "text": "你好"}]}},
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"jsonrpc", "id", "error"}
    assert body["error"]["code"] == -32602
    assert len(recorded) == 1
    assert recorded[0]["detail"]["errorType"] == "BadRequestError"
    assert recorded[0]["detail"]["errorStatus"] == 400


@pytest.mark.parametrize(
    ("exc", "expected_status", "expected_code", "expected_type"),
    [
        # 跨租户附件：修复前是 **403**（等于向对端确认「该附件存在于别的租户」），且零流水
        (ForbiddenError("无权访问该租户资源"), 404, -32001, "ForbiddenError"),
        # 附件未就绪：修复前是 400 但**零流水**（与 docstring 的「成败都留一条」相矛盾）
        (BadRequestError("附件文件未就绪"), 400, -32602, "BadRequestError"),
    ],
)
@pytest.mark.asyncio
async def test_artifact_endpoint_failure_maps_status_and_audits(  # noqa: ANN001
    as_a2a, api_client, monkeypatch, exc, expected_status, expected_code, expected_type
):
    """E1 的 HTTP 面：该端点是普通 HTTP 下载，形状本来就是平台信封 —— 要验的是**状态码**与**留痕**。

    非 ``AppError``（存储故障）→ 500 的情形不在本用例：``ASGITransport`` 默认
    ``raise_app_exceptions=True``，应用层重抛的异常会在测试客户端里直接抛出，拿不到响应。
    该情形由服务层用例（`test_read_task_artifact_audits_storage_failure_and_reraises`）锁定。
    """
    attachment_id, task_id = uuid4(), uuid4()
    job = SimpleNamespace(
        id=task_id,
        status=SimpleNamespace(value="success"),
        params={},
        result={"kind": "image", "attachment_ids": [str(attachment_id)], "mime_type": "image/png"},
        source_ref_type="agent",
        source_ref_id=AGENT_ID,
    )

    async def _owned(_db, _ctx, _job_id):  # noqa: ANN001
        return job

    class _FailingAttachments:
        def __init__(self, _db, _ctx) -> None:
            pass

        async def read_attachment_bytes(self, _attachment_id):  # noqa: ANN001
            raise exc

    recorded: list[dict] = []

    async def _write(**kwargs):  # noqa: ANN003
        recorded.append(kwargs)

    # 本路由只用这三个 I/O 出口（取任务 / 读字节 / 审计），其余全真，让请求经 ASGI 走完一次分发
    monkeypatch.setattr(a2a_svc, "get_generative_job_for_tenant", _owned)
    monkeypatch.setattr(a2a_svc, "AttachmentService", _FailingAttachments)
    monkeypatch.setattr(a2a_svc, "write_a2a_audit", _write)

    resp = await api_client.get(ARTIFACT_PATH.format(AGENT_ID, task_id, attachment_id))

    assert resp.status_code == expected_status
    body = resp.json()
    assert set(body) == {"code", "message", "data", "trace_id"}
    # 平台信封的 ``code`` 与 HTTP 状态码同值（全局处理器 ``_error_envelope`` 用 ``exc.code``，
    # 即 ``status_code``；本路由的 429 分支亦为 ``"code": 429``）。审计里的 ``errorCode`` 才是
    # A2A 域码（见下方断言），两者不可混为一谈。
    assert body["code"] == expected_status
    assert len(recorded) == 1
    assert recorded[0]["action"] == "a2a.artifact.download"
    assert recorded[0]["outcome"] == "failed"
    assert recorded[0]["detail"]["errorCode"] == expected_code
    assert recorded[0]["detail"]["errorType"] == expected_type


@pytest.mark.asyncio
async def test_rpc_view_converts_escaped_app_error_to_envelope(as_a2a, api_client, monkeypatch):
    """视图层兜底（纵深防御）：分发点逸出的 `AppError` 仍回 JSON-RPC 信封。

    **注入式用例**：两个流式入口当前无可达的 `AppError` 逸出点，故这里用替身直接把异常
    从分发点抛出 —— 它锁的是「这段兜底不被重构悄悄删掉」，**不是**缺陷回归闸门。
    """

    async def _escape(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise ForbiddenError("配额已用尽")

    monkeypatch.setattr(view_mod, "handle_a2a_rpc", _escape)

    resp = await api_client.post(
        RPC_PATH,
        json={"jsonrpc": "2.0", "id": 11, "method": "message/send", "params": {}},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"jsonrpc", "id", "error"}
    assert body["error"]["code"] == -32602
