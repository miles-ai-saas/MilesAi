"""HTTP 访问日志中间件。"""

import logging

from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.apps.application import create_app


def test_access_log_emits_for_api_route(caplog):
    router = APIRouter()

    @router.get("/ping-access-log")
    async def ping():
        return {"ok": True}

    app = create_app()
    app.include_router(router, prefix="/api/v1")

    with caplog.at_level(logging.INFO, logger="app.http.access"):
        client = TestClient(app, raise_server_exceptions=True)
        r = client.get("/api/v1/ping-access-log", headers={"X-Trace-Id": "trace-test-1"})

    assert r.status_code == 200
    assert r.headers.get("X-Trace-Id") == "trace-test-1"
    joined = "\n".join(r.message for r in caplog.records)
    assert "GET" in joined
    assert "/api/v1/ping-access-log" in joined
    assert "200" in joined
    assert "trace-test-1" in joined


def test_access_log_skips_health(caplog):
    app = create_app()
    with caplog.at_level(logging.INFO, logger="app.http.access"):
        client = TestClient(app)
        client.get("/api/v1/health")

    assert not [r for r in caplog.records if r.name == "app.http.access"]
