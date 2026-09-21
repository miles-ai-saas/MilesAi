"""A2A 客户端出站鉴权头。

``agt_a2a_peers.auth_config`` 此前只落库、从不参与请求，导致「平台对外发布的智能体
（须 X-API-Key）」无法被本平台自己的 Peer 登记调用 —— 暴露面有了、闭环断了。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from miles_portal.tenant.a2a.card_client import fetch_agent_card
from miles_portal.tenant.a2a.client import _pick_rpc_url, build_auth_headers, invoke_a2a_peer
from miles_portal.tenant.a2a.server import build_agent_card


def test_api_key_variants_map_to_x_api_key_header():
    assert build_auth_headers({"api_key": "k-1"}) == {"X-API-Key": "k-1"}
    assert build_auth_headers({"x_api_key": "k-2"}) == {"X-API-Key": "k-2"}


def test_bearer_token_maps_to_authorization_header():
    assert build_auth_headers({"bearer_token": "t"}) == {"Authorization": "Bearer t"}


def test_custom_headers_are_passed_through_and_merged_with_api_key():
    headers = build_auth_headers({"api_key": "k", "headers": {"X-Tenant": "acme"}})
    assert headers == {"X-API-Key": "k", "X-Tenant": "acme"}


def test_empty_or_invalid_config_yields_no_headers():
    assert build_auth_headers({}) == {}
    assert build_auth_headers(None) == {}
    # 脏数据不产生半截鉴权头（如把 dict 直接塞给 api_key）
    assert build_auth_headers({"api_key": {"nested": True}}) == {}
    assert build_auth_headers({"headers": ["not", "a", "dict"]}) == {}


def test_blank_values_are_ignored():
    assert build_auth_headers({"api_key": "   ", "bearer_token": ""}) == {}


# --- HTTP 层：确认头真的发出去了（纯函数正确但没接线也是白搭） --------------------


class _FakeResponse:
    status_code = 200

    def __init__(self, data: dict) -> None:
        self._data = data

    def raise_for_status(self) -> None:  # noqa: D102
        return None

    def json(self) -> dict:  # noqa: D102
        return self._data


class _FakeClient:
    """最小 httpx.AsyncClient 替身，记录 get/post 收到的 headers。"""

    def __init__(self, captured: dict, get_data: dict, post_data: dict) -> None:
        self._captured = captured
        self._get_data = get_data
        self._post_data = post_data

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def get(self, _url: str, headers: dict | None = None) -> _FakeResponse:
        self._captured["get"] = headers or {}
        return _FakeResponse(self._get_data)

    async def post(self, url: str, *, json: dict | None = None, headers: dict | None = None) -> _FakeResponse:
        self._captured["post"] = headers or {}
        self._captured["post_body"] = json
        self._captured.setdefault("post_urls", []).append(url)
        return _FakeResponse(self._post_data)


def _patch_client(monkeypatch, captured: dict, get_data: dict, post_data: dict) -> None:
    monkeypatch.setattr(
        "miles_portal.tenant.a2a.card_client.httpx.AsyncClient",
        lambda **_kwargs: _FakeClient(captured, get_data, post_data),
    )
    monkeypatch.setattr(
        "miles_portal.tenant.a2a.client.httpx.AsyncClient",
        lambda **_kwargs: _FakeClient(captured, get_data, post_data),
    )


@pytest.mark.asyncio
async def test_fetch_agent_card_sends_configured_auth(monkeypatch):  # noqa: ANN001
    captured: dict = {}
    _patch_client(monkeypatch, captured, {"name": "Peer"}, {})

    card, _url = await fetch_agent_card("https://peer.example.com", auth_config={"api_key": "k-1"})

    assert card["name"] == "Peer"
    assert captured["get"]["X-API-Key"] == "k-1"


def test_pick_rpc_url_uses_declared_supported_interface_url():
    """v1.0 对端的 ``supportedInterfaces[].url`` 是端点，``protocolBinding`` 只是传输标签。

    回归：此前先读 ``protocolBinding``（恒为 ``JSONRPC``、不以 http 开头），导致平台自己
    产出的 Card 的 ``url`` 被忽略、退回 ``base_url``（通常只是 host 根），反向把本平台
    发布的智能体登记为 Peer 时必然调不通。
    """
    peer = SimpleNamespace(
        agent_card_json={"supportedInterfaces": [{"url": "https://peer.example.com/api/v1/open/a2a/agents/abc", "protocolBinding": "JSONRPC"}]},
        base_url="https://peer.example.com",
        agent_card_url="https://peer.example.com/.well-known/agent-card.json",
    )

    assert _pick_rpc_url(peer) == "https://peer.example.com/api/v1/open/a2a/agents/abc"


def test_pick_rpc_url_reads_v03_additional_interfaces():
    """0.3 对端的接口数组叫 ``additionalInterfaces``，传输标签是 ``transport``。"""
    peer = SimpleNamespace(
        agent_card_json={"additionalInterfaces": [{"url": "https://peer.example.com/a2a", "transport": "JSONRPC"}]},
        base_url="https://peer.example.com",
        agent_card_url="https://peer.example.com/.well-known/agent-card.json",
    )

    assert _pick_rpc_url(peer) == "https://peer.example.com/a2a"


def test_pick_rpc_url_consumes_our_own_emitted_card():
    """自家产出的 Card 必须能被自家客户端解析出端点。

    否则「发布智能体 → 反向登记为 Peer」这条自环路径会静默退回 ``base_url``（host 根），
    调不通却没有任何报错。
    """
    card = build_agent_card(agent_id="abc", name="客服助手", description=None, base_url="https://miles.example.com")
    peer = SimpleNamespace(
        agent_card_json=card,
        base_url="https://miles.example.com",
        agent_card_url="https://miles.example.com/.well-known/agent-card.json",
    )

    assert _pick_rpc_url(peer) == "https://miles.example.com/api/v1/open/a2a/agents/abc"


@pytest.mark.asyncio
async def test_invoke_a2a_peer_sends_configured_auth(monkeypatch):  # noqa: ANN001
    captured: dict = {}
    _patch_client(monkeypatch, captured, {}, {"result": {"text": "收到"}})

    peer = SimpleNamespace(
        name="Peer",
        status=SimpleNamespace(value="active"),
        agent_card_json={"supportedInterfaces": [{"url": "https://peer.example.com/a2a", "protocolBinding": "JSONRPC"}]},
        agent_card_url="https://peer.example.com/.well-known/agent-card.json",
        base_url="https://peer.example.com",
        card_display_name="Peer",
        auth_config={"api_key": "k-2"},
    )

    answer = await invoke_a2a_peer(peer, "你好")

    assert answer == "收到"
    assert captured["post"]["X-API-Key"] == "k-2"
    assert captured["post"]["Content-Type"] == "application/json"
    # 必须打到 Card 声明的端点，而非 base_url（host 根）
    assert captured["post_urls"][0] == "https://peer.example.com/a2a/message/send"
    # 0.3 的 Part 判别键是 kind：发 type 会被严格的对端当未知 part 丢掉
    assert captured["post_body"]["params"]["message"]["parts"] == [{"kind": "text", "text": "你好"}]
