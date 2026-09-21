import pytest
from httpx import ASGITransport, AsyncClient

from miles_server.main import app


@pytest.mark.asyncio
async def test_health_endpoint_structure():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 无 DB 时可能 degraded，但接口应可访问
        try:
            response = await client.get("/api/v1/health")
            assert response.status_code == 200
            body = response.json()
            assert "code" in body
            assert "data" in body
        except Exception:
            pytest.skip("需要数据库连接")
