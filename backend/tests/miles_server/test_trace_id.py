import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from miles_server.main import app


@pytest.mark.asyncio
async def test_success_response_includes_trace_id_in_body():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            response = await client.get("/api/v1/health")
        except Exception:
            pytest.skip("需要数据库连接")
        assert response.status_code == 200
        body = response.json()
        assert body.get("trace_id")
        assert response.headers.get("x-trace-id") == body["trace_id"]


@pytest.mark.asyncio
async def test_trace_id_propagates_from_request_header():
    custom = str(uuid.uuid4())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            response = await client.get(
                "/api/v1/health",
                headers={"X-Trace-Id": custom},
            )
        except Exception:
            pytest.skip("需要数据库连接")
        assert response.status_code == 200
        body = response.json()
        assert body["trace_id"] == custom
        assert response.headers.get("x-trace-id") == custom
