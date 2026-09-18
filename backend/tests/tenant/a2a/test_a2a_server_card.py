"""A2A Server（对外暴露）：Card 构造、发布门槛、JSON-RPC 信封与文本解析。

与 ``test_a2a_card_client.py``（拉取远端 Card）方向相反，本文件覆盖本平台产 Card、
收 ``message/send`` 的一侧。纯函数与服务分别验证：
1. ``miles_portal.tenant.a2a.server`` 的 Card / 信封 / parts 解析（无 DB）；
2. ``a2a.services.server`` 的发布门槛与默认发布智能体解析（fake DB）。
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_core.models.agent import Agent, AgentStatus, AgentType
from miles_portal.tenant.a2a import server as server_mod
from miles_portal.tenant.a2a.server import (
    A2A_PUBLISH_FLAG,
    build_agent_card,
    extract_message_text,
    is_publish_enabled,
    jsonrpc_error,
    jsonrpc_result,
)
from miles_portal.tenant.a2a.services import server as server_svc

AGENT_ID = uuid4()
BASE = "https://miles.example.com"


# --- 1. 纯函数 ---------------------------------------------------------------


def test_is_publish_enabled_reads_config_flag():
    assert is_publish_enabled({A2A_PUBLISH_FLAG: True}) is True
    assert is_publish_enabled({A2A_PUBLISH_FLAG: "true"}) is False
    assert is_publish_enabled({A2A_PUBLISH_FLAG: False}) is False
    assert is_publish_enabled({}) is False
    assert is_publish_enabled(None) is False


def test_build_agent_card_declares_rpc_interface_and_fallback_skill():
    card = build_agent_card(agent_id=AGENT_ID, name="客服助手", description="解答售后问题", base_url=BASE)

    assert card["name"] == "客服助手"
    assert card["description"] == "解答售后问题"
    rpc_url = f"{BASE}/api/v1/open/a2a/agents/{AGENT_ID}"
    assert card["url"] == rpc_url
    assert card["supportedInterfaces"] == [{"url": rpc_url, "protocolBinding": "JSONRPC", "protocolVersion": server_mod.A2A_PROTOCOL_VERSION}]
    # 未绑定技能包时，智能体自身即一个 skill（Card 不允许 skills 为空数组）
    assert [s["id"] for s in card["skills"]] == [str(AGENT_ID)]
    assert card["skills"][0]["name"] == "客服助手"


def test_build_agent_card_declares_api_key_security_scheme():
    """Card 须声明调用端点的鉴权方式，否则标准 A2A 客户端无从得知要带 ``X-API-Key``。"""
    card = build_agent_card(agent_id=AGENT_ID, name="客服助手", description="D", base_url=BASE)

    assert card["securitySchemes"] == {
        "apiKey": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "该智能体的 API Key，在智能体详情中创建",
        }
    }
    assert card["security"] == [{"apiKey": []}]


def test_declared_security_header_matches_actual_auth_header():
    """Card 声明的头名必须与实际鉴权头一致 —— 二者漂移会让对端带着错误的头调用。

    生产侧共用同一常量，本测试直接比对「Card 声明」与「FastAPI 依赖实际读取的 alias」。
    """
    from miles_portal.tenant.agents.deps_api_auth import require_agent_api_key

    card = build_agent_card(agent_id=AGENT_ID, name="N", description=None, base_url=BASE)
    declared = card["securitySchemes"]["apiKey"]["name"]

    param = inspect.signature(require_agent_api_key).parameters["x_api_key"]
    assert declared == param.default.alias


def test_build_agent_card_base_url_trailing_slash_is_normalized():
    card = build_agent_card(agent_id=AGENT_ID, name="N", description=None, base_url=f"{BASE}/")
    assert card["url"] == f"{BASE}/api/v1/open/a2a/agents/{AGENT_ID}"
    assert card["description"] == ""


def test_build_agent_card_uses_bound_skill_packages_when_present():
    skills = [{"id": "skill:faq", "name": "FAQ", "description": "常见问题", "tags": ["售后"]}]
    card = build_agent_card(agent_id=AGENT_ID, name="N", description="D", base_url=BASE, skills=skills)
    assert card["skills"] == skills


def test_extract_message_text_joins_text_parts():
    params = {
        "message": {
            "role": "user",
            "parts": [{"type": "text", "text": "你好"}, {"type": "text", "text": "在吗"}],
        }
    }
    assert extract_message_text(params) == "你好\n在吗"


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"message": {}},
        {"message": {"parts": []}},
        {"message": {"parts": [{"type": "file", "file": {}}]}},
        {"message": {"parts": [{"type": "text", "text": "   "}]}},
    ],
)
def test_extract_message_text_rejects_payload_without_text(params):
    """缺少文本属调用方参数错误；静默返回空串会让本平台空转一轮对话。"""
    with pytest.raises(BadRequestError):
        extract_message_text(params)


def test_jsonrpc_envelopes():
    assert jsonrpc_result("1", {"ok": True}) == {"jsonrpc": "2.0", "id": "1", "result": {"ok": True}}
    err = jsonrpc_error("1", server_mod.METHOD_NOT_FOUND, "不支持的方法")
    assert err["jsonrpc"] == "2.0"
    assert err["id"] == "1"
    assert err["error"] == {"code": server_mod.METHOD_NOT_FOUND, "message": "不支持的方法"}
    assert "result" not in err


# --- 2. 服务：发布门槛 --------------------------------------------------------


def _agent(**overrides):
    agent = Agent()
    agent.id = AGENT_ID
    agent.name = "客服助手"
    agent.description = "D"
    agent.agent_type = AgentType.CUSTOM
    agent.status = AgentStatus.ENABLED
    agent.config = {A2A_PUBLISH_FLAG: True}
    agent.deleted_at = None
    for key, value in overrides.items():
        setattr(agent, key, value)
    return agent


class _Db:
    """最小 fake：``get`` 返回预置智能体，``execute`` 返回预置行。"""

    def __init__(self, agent=None, rows=None):
        self._agent = agent
        self._rows = rows or []

    async def get(self, _model, _id):  # noqa: ANN001
        return self._agent

    async def execute(self, _stmt):  # noqa: ANN001
        return SimpleNamespace(scalars=lambda: iter(self._rows))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("agent_type", "status", "flag", "deleted"),
    [
        (AgentType.A2A, AgentStatus.ENABLED, True, False),  # 互联宿主是调用方，不对外
        (AgentType.CUSTOM, AgentStatus.DISABLED, True, False),
        (AgentType.CUSTOM, AgentStatus.ENABLED, False, False),
        (AgentType.CUSTOM, AgentStatus.ENABLED, True, True),  # 已软删
    ],
)
async def test_load_published_agent_rejects_unpublished(monkeypatch, agent_type, status, flag, deleted):  # noqa: ANN001
    monkeypatch.setattr(server_svc, "is_marked_deleted", lambda _row: deleted)
    agent = _agent(agent_type=agent_type, status=status, config={A2A_PUBLISH_FLAG: flag})
    with pytest.raises(NotFoundError):
        await server_svc.load_published_agent(_Db(agent=agent), AGENT_ID)


@pytest.mark.asyncio
async def test_load_published_agent_returns_enabled_custom_with_flag(monkeypatch):  # noqa: ANN001
    monkeypatch.setattr(server_svc, "is_marked_deleted", lambda _row: False)
    agent = _agent()
    assert await server_svc.load_published_agent(_Db(agent=agent), AGENT_ID) is agent


@pytest.mark.asyncio
async def test_build_public_agent_card_maps_bound_skills(monkeypatch):  # noqa: ANN001
    monkeypatch.setattr(server_svc, "is_marked_deleted", lambda _row: False)
    monkeypatch.setattr(
        server_svc,
        "_bound_skill_entries",
        _async_ret([{"id": "skill:faq", "name": "FAQ", "description": None, "tags": []}]),
    )
    card = await server_svc.build_public_agent_card(_Db(agent=_agent()), _agent(), base_url=BASE)
    assert [s["id"] for s in card["skills"]] == ["skill:faq"]


@pytest.mark.asyncio
async def test_build_agent_card_by_id_gates_on_publish(monkeypatch):  # noqa: ANN001
    """API 声明层唯一入口：未发布不返回 Card。"""
    monkeypatch.setattr(server_svc, "is_marked_deleted", lambda _row: False)
    monkeypatch.setattr(server_svc, "_bound_skill_entries", _async_ret([]))

    with pytest.raises(NotFoundError):
        await server_svc.build_agent_card_by_id(_Db(agent=None), AGENT_ID, base_url=BASE)

    card = await server_svc.build_agent_card_by_id(_Db(agent=_agent()), AGENT_ID, base_url=BASE)
    assert card["name"] == "客服助手"


def _async_ret(value):
    async def _inner(*_args, **_kwargs):
        return value

    return _inner


@pytest.mark.asyncio
async def test_resolve_default_published_agent_requires_unambiguous_match():
    """根路径别名只在全平台唯一发布时可用；0 或 >1 都不猜，返回 None。"""
    assert await server_svc.resolve_default_published_agent_id(_Db(rows=[])) is None
    assert await server_svc.resolve_default_published_agent_id(_Db(rows=[AGENT_ID, uuid4()])) is None
    assert await server_svc.resolve_default_published_agent_id(_Db(rows=[AGENT_ID])) == AGENT_ID


# --- 3. JSON-RPC 分发 ---------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_rpc_message_send_returns_agent_message(monkeypatch):  # noqa: ANN001
    async def fake_chat(_db, _ctx, _agent_id, text):  # noqa: ANN001
        assert text == "帮我查订单"
        return "订单已发货"

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    payload = {
        "jsonrpc": "2.0",
        "id": "abc",
        "method": "message/send",
        "params": {"message": {"role": "user", "parts": [{"type": "text", "text": "帮我查订单"}]}},
    }
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload)

    assert envelope["jsonrpc"] == "2.0"
    assert envelope["id"] == "abc"
    result = envelope["result"]
    assert result["kind"] == "message"
    assert result["role"] == "agent"
    assert result["parts"][0]["text"] == "订单已发货"
    assert result["messageId"]


@pytest.mark.asyncio
async def test_handle_rpc_rejects_non_jsonrpc_payload():
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, ["not", "a", "dict"])
    assert envelope["error"]["code"] == server_mod.INVALID_REQUEST
    assert "result" not in envelope


@pytest.mark.asyncio
async def test_handle_rpc_rejects_unsupported_method():
    payload = {"jsonrpc": "2.0", "id": 1, "method": "message/stream", "params": {}}
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload)
    assert envelope["error"]["code"] == server_mod.METHOD_NOT_FOUND
    assert "message/stream" in envelope["error"]["message"]


@pytest.mark.asyncio
async def test_handle_rpc_maps_missing_text_to_invalid_params():
    payload = {"jsonrpc": "2.0", "id": 1, "method": "message/send", "params": {"message": {"parts": []}}}
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload)
    assert envelope["error"]["code"] == server_mod.INVALID_PARAMS


@pytest.mark.asyncio
async def test_handle_rpc_maps_agent_failure_to_internal_error(monkeypatch):  # noqa: ANN001
    """对话链路异常必须转 JSON-RPC 错误：抛栈会让对端只看到 HTTP 500 无正文。"""

    async def boom(*_args, **_kwargs):
        raise RuntimeError("模型不可用")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", boom)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {"message": {"parts": [{"type": "text", "text": "hi"}]}},
    }
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload)
    assert envelope["error"]["code"] == server_mod.INTERNAL_ERROR
    assert "模型不可用" in envelope["error"]["message"]
