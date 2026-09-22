"""HTTP API 轻量 E2E：鉴权、meta、流程编译/试运行（依赖 override，无真实 DB）。"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from miles_core.deps import get_tenant_context
from miles_core.infra.db import get_db
from miles_core.tenant import TenantContext
from miles_portal.tenant.flows.schemas.flow import FlowRunResponse
from miles_server.apps.application import create_app
from tests.conftest import disable_platform_risk, make_tenant_ctx


@pytest.mark.asyncio
async def test_flows_meta_returns_enum_dictionary(api_client):
    response = await api_client.get("/api/v1/flows/meta")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"] is not None
    assert "statuses" in body["data"]


@pytest.mark.asyncio
async def test_flows_templates_lists_builtin_graphs(api_client):
    response = await api_client.get("/api/v1/flows/templates")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    items = body["data"]["items"]
    assert isinstance(items, list)
    assert len(items) >= 1
    assert "graph_json" in items[0]


@pytest.mark.asyncio
async def test_kb_meta_returns_enum_dictionary(api_client):
    response = await api_client.get("/api/v1/kb/meta")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"] is not None


@pytest.mark.asyncio
async def test_meta_requires_auth_without_override():
    with disable_platform_risk():
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/flows/meta")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_meta_forbidden_without_permission():
    with disable_platform_risk():
        app = create_app()
        ctx = make_tenant_ctx(permissions=frozenset(), is_superuser=False)

        async def override_ctx() -> TenantContext:
            return ctx

        async def override_db():
            yield AsyncMock()

        app.dependency_overrides[get_tenant_context] = override_ctx
        app.dependency_overrides[get_db] = override_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/flows/meta")
        app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_flow_compile_endpoint(api_client):
    flow_id = uuid4()
    report = {
        "compilable": True,
        "engine": "langgraph",
        "node_order": ["out_1"],
        "node_types": ["TextOutput"],
        "execution_layers": [["out_1"]],
        "parallel_groups": [],
        "conditional_nodes": [],
        "errors": [],
        "error_details": [],
    }
    with patch(
        "miles_portal.tenant.flows.views.flows.FlowService.compile_preview",
        new_callable=AsyncMock,
        return_value=report,
    ):
        response = await api_client.post(f"/api/v1/flows/{flow_id}/compile")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["compilable"] is True
    assert body["data"]["engine"] == "langgraph"


@pytest.mark.asyncio
async def test_flow_run_endpoint(api_client):
    flow_id = uuid4()
    run_result = FlowRunResponse(output="hello api", steps=[{"type": "graph_start"}])
    with patch(
        "miles_portal.tenant.flows.views.flows.FlowService.run",
        new_callable=AsyncMock,
        return_value=run_result,
    ):
        response = await api_client.post(
            f"/api/v1/flows/{flow_id}/run",
            json={"inputs": {"query": "hello api"}},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["output"] == "hello api"
    assert body["data"]["steps"]
