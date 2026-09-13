"""pytest 全局 fixture / 环境。"""

import os
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

# LiteLLM 在 import 时会尝试预加载 AWS Bedrock/SageMaker schema；未装 botocore 时会打 WARNING。
os.environ.setdefault("LITELLM_LOG", "ERROR")

from miles_core.deps import get_tenant_context
from miles_core.infra.db import get_db
from miles_core.tenant import TenantContext
from miles_server.apps.application import create_app


def make_tenant_ctx(*, permissions: frozenset[str] | None = None, is_superuser: bool = True) -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="tester",
        is_superuser=is_superuser,
        permissions=permissions if permissions is not None else frozenset(["flow:read", "flow:write", "kb:read", "kb:write"]),
    )


@contextmanager
def disable_platform_risk() -> Iterator[None]:
    """API 测试绕过 Redis 限流/黑名单中间件。"""
    with (
        patch(
            "miles_core.web.middlewares.platform_risk.platform_risk_enforcer.is_ip_blocked",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "miles_core.web.middlewares.platform_risk.platform_risk_enforcer.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(False, None),
        ),
    ):
        yield


@pytest.fixture
def api_app():
    with disable_platform_risk():
        app = create_app()
        ctx = make_tenant_ctx()

        async def override_ctx() -> TenantContext:
            return ctx

        async def override_db() -> AsyncIterator[AsyncMock]:
            yield AsyncMock()

        app.dependency_overrides[get_tenant_context] = override_ctx
        app.dependency_overrides[get_db] = override_db
        yield app
        app.dependency_overrides.clear()


@pytest.fixture
async def api_client(api_app):
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
