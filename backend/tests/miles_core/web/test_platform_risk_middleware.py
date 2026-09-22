"""平台风控中间件：``/api/v1`` 全局限流必须按来源 IP 维度计算。

为什么单独立一条：``ip`` 维度全仓只有这一个调用点，而「维度传错」不会让任何请求报错 ——
只表现为全局限流形同虚设（规则在库里、却永远不参与计数）。服务层的用例看不到中间件传了
什么维度，故在此直接锁住它传给 enforcer 的 ``scope`` 与计数键。
"""

from __future__ import annotations

import pytest
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from miles_core.models.risk import RateLimitScope
from miles_core.risk import enforce as enforce_mod
from miles_core.web.middlewares.platform_risk import PlatformRiskMiddleware


def _request(path: str, *, client: tuple[str, int] = ("203.0.113.7", 51234)) -> Request:
    """最小 ASGI scope 的 ``Request``：``dispatch`` 只用到 path / headers / client。"""
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "query_string": b"",
            "headers": [],
            "client": client,
            "scheme": "http",
            "server": ("testserver", 80),
            "root_path": "",
        }
    )


async def _ok(_request: Request) -> Response:
    """放行替身：证明未命中时中间件不改变调用链。"""
    return PlainTextResponse("ok")


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

    response = await PlatformRiskMiddleware(app=None).dispatch(_request("/api/v1/chat"), _ok)

    assert response.status_code == 200
    assert seen["path"] == "/api/v1/chat"
    # 计数键必须是来源 IP，而非某个租户/Key 标识：否则同一 NAT 出口下的两个对端会互相连坐
    assert seen["client_key"] == "203.0.113.7"
    assert seen["scope"] is RateLimitScope.IP
