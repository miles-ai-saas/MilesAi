"""CORS：白名单取自 ``CORS_ORIGINS``，且错误响应头与中间件保持一致。

回归背景：``create_app`` 曾硬编码 ``allow_origin_regex=r".*"`` + ``allow_credentials=True``，
使 ``CORS_ORIGINS`` 成为死配置，且与异常响应的 ``_cors_headers``（仅放行白名单）不一致。
"""

from fastapi import APIRouter
from fastapi.testclient import TestClient

from miles_core.config import get_settings
from miles_server.apps.application import create_app

ALLOWED_ORIGIN = "https://ui.example.com"
OTHER_ORIGIN = "https://evil.example.com"


def _client(monkeypatch, *, cors_origins: str = ALLOWED_ORIGIN, allow_credentials: bool = False) -> TestClient:
    """先改配置再建 app：中间件在 ``create_app`` 时读配置，顺序不能反。"""
    settings = get_settings()
    monkeypatch.setattr(settings, "cors_origins", cors_origins)
    monkeypatch.setattr(settings, "cors_allow_credentials", allow_credentials)

    router = APIRouter()

    @router.get("/ok")
    async def ok():
        return {"ok": True}

    @router.get("/boom")
    async def boom():
        raise RuntimeError("boom")

    app = create_app()
    app.include_router(router, prefix="/_test")
    return TestClient(app, raise_server_exceptions=False)


def test_allowed_origin_is_echoed(monkeypatch):
    r = _client(monkeypatch).get("/_test/ok", headers={"Origin": ALLOWED_ORIGIN})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


def test_disallowed_origin_is_not_allowed(monkeypatch):
    """核心回归：白名单外的来源不得再被放行（旧行为为 ``.*``）。"""
    r = _client(monkeypatch).get("/_test/ok", headers={"Origin": OTHER_ORIGIN})
    assert r.status_code == 200
    assert "access-control-allow-origin" not in r.headers


def test_preflight_from_allowed_origin(monkeypatch):
    r = _client(monkeypatch).options(
        "/_test/ok",
        headers={"Origin": ALLOWED_ORIGIN, "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


def test_credentials_not_advertised_by_default(monkeypatch):
    """认证走 Bearer Header、无 Cookie，默认不应回 ``Allow-Credentials: true``。"""
    r = _client(monkeypatch).get("/_test/ok", headers={"Origin": ALLOWED_ORIGIN})
    assert r.headers.get("access-control-allow-credentials") != "true"


def test_error_response_matches_middleware_cors(monkeypatch):
    """异常响应头须与中间件一致：白名单内放行、且不附带凭证。"""
    r = _client(monkeypatch).get("/_test/boom", headers={"Origin": ALLOWED_ORIGIN})
    assert r.status_code == 500
    assert r.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    assert r.headers.get("access-control-allow-credentials") != "true"


def test_error_response_from_disallowed_origin(monkeypatch):
    r = _client(monkeypatch).get("/_test/boom", headers={"Origin": OTHER_ORIGIN})
    assert r.status_code == 500
    assert "access-control-allow-origin" not in r.headers


def test_credentials_opt_in_advertises_header(monkeypatch):
    """显式开启（CORS_ALLOW_CREDENTIALS=true）时才回 Allow-Credentials。"""
    r = _client(monkeypatch, allow_credentials=True).get("/_test/ok", headers={"Origin": ALLOWED_ORIGIN})
    assert r.headers.get("access-control-allow-credentials") == "true"
