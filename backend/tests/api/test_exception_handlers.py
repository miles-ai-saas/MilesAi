"""全局异常处理器：统一 JSON 信封。"""

from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy.exc import ProgrammingError

from miles_server.apps.application import create_app


def test_unhandled_db_error_returns_api_envelope_not_plaintext_traceback():
    router = APIRouter()

    @router.get("/boom")
    async def boom():
        raise ProgrammingError("SELECT 1", {}, Exception("column deleted_at does not exist"))

    app = create_app()
    app.include_router(router, prefix="/_test")

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/_test/boom")

    assert r.status_code == 500
    assert "application/json" in (r.headers.get("content-type") or "")
    body = r.json()
    assert body["code"] == 500
    assert body["data"] is None
    assert "message" in body
    assert not r.text.strip().startswith("Traceback")
