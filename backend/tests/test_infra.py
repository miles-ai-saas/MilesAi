"""基础设施探测与健康检查单元测试。"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.tenant import TenantContext
from app.tenant.system.services.infra import InfraService
from app.utils.health_checks import (
    COMPONENT_IDS,
    build_infra_settings_preview,
    probe_component,
    probe_components,
)


@pytest.mark.asyncio
async def test_probe_component_unknown():
    result = await probe_component("unknown")
    assert result["status"] == "skipped"
    assert result["message"] == "未知组件"


@pytest.mark.asyncio
async def test_probe_component_postgres_ok():
    with patch("app.utils.health_checks.check_postgres", new_callable=AsyncMock, return_value=True):
        result = await probe_component("postgres")
    assert result["status"] == "ok"
    assert result["id"] == "postgres"
    assert result["latency_ms"] is not None


@pytest.mark.asyncio
async def test_probe_components_default_all():
    with patch(
        "app.utils.health_checks.probe_component",
        new_callable=AsyncMock,
        side_effect=lambda cid: {"id": cid, "status": "ok"},
    ):
        results = await probe_components()
    assert len(results) == len(COMPONENT_IDS)


def test_build_infra_settings_preview_masks_secrets():
    preview = build_infra_settings_preview()
    assert preview["celery_broker"] == "***"
    assert "postgres" in preview
    assert preview["postgres"]


@pytest.mark.asyncio
async def test_infra_service_test_connection():
    ctx = TenantContext(
        tenant_id=uuid4(),
        user_id=uuid4(),
        username="admin",
        is_superuser=True,
        permissions=frozenset(),
    )
    svc = InfraService(AsyncMock(), ctx)
    with patch(
        "app.tenant.system.services.infra.probe_components",
        new_callable=AsyncMock,
        return_value=[
            {
                "id": "redis",
                "label": "Redis",
                "status": "ok",
                "latency_ms": 1,
                "message": None,
            }
        ],
    ):
        out = await svc.test_connection(["redis"])
    assert len(out.results) == 1
    assert out.results[0].status == "ok"
