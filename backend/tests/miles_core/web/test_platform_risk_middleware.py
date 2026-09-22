"""平台风控中间件：``/api/v1`` 全局限流必须按来源 IP 维度计算。

为什么单独立一条：``ip`` 维度全仓只有这一个调用点，而「维度传错」不会让任何请求报错 ——
只表现为全局限流形同虚设（规则在库里、却永远不参与计数）。服务层的用例看不到中间件传了
什么维度，故在此直接锁住它传给 enforcer 的 ``scope`` 与计数键。
"""

from __future__ import annotations

import pytest

from miles_core.models.risk import RateLimitScope
from miles_core.risk import enforce as enforce_mod
from miles_core.web.middlewares.platform_risk import PlatformRiskMiddleware


def _http_scope(path: str, *, client: tuple[str, int] = ("203.0.113.7", 51234)) -> dict:
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": client,
        "server": ("testserver", 80),
        "scheme": "http",
        "root_path": "",
    }


async def _ok_app(scope, receive, send):  # noqa: ANN001
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


async def _empty_receive():
    return {"type": "http.disconnect"}


@pytest.mark.asyncio
async def test_middleware_checks_rate_limit_on_ip_dimension(monkeypatch):  # noqa: ANN001
    """全局限流按 IP 维度调用；写成 ``API_KEY`` 会让 ip 规则永不参与计数。"""
    seen: dict = {}

    async def fake_check(path, client_key, *, scope):  # noqa: ANN001
        seen.update(path=path, client_key=client_key, scope=scope)
        return None

    async def not_blocked(_ip: str) -> bool:
        return False

    monkeypatch.setattr(enforce_mod.platform_risk_enforcer, "check_rate_limit", fake_check)
    monkeypatch.setattr(enforce_mod.platform_risk_enforcer, "is_ip_blocked", not_blocked)

    messages: list[dict] = []

    async def capture_send(message):  # noqa: ANN001
        messages.append(message)

    await PlatformRiskMiddleware(_ok_app)(_http_scope("/api/v1/chat"), _empty_receive, capture_send)

    assert messages[0]["type"] == "http.response.start"
    assert messages[0]["status"] == 200
    assert seen["path"] == "/api/v1/chat"
    # 计数键必须是来源 IP，而非某个租户/Key 标识：否则同一 NAT 出口下的两个对端会互相连坐
    assert seen["client_key"] == "203.0.113.7"
    assert seen["scope"] is RateLimitScope.IP
