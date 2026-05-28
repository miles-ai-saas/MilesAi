"""应用市场 review_mode 行为测试。"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.common.exceptions import ForbiddenError
from app.core.tenant import TenantContext
from app.marketplace.review_config import (
    normalize_review_mode,
    require_platform_review_allowed,
    require_tenant_review_allowed,
)


def test_normalize_review_mode_defaults():
    assert normalize_review_mode(None) == "platform"
    assert normalize_review_mode("tenant") == "tenant"
    assert normalize_review_mode("invalid") == "platform"


@pytest.mark.asyncio
async def test_tenant_review_blocked_in_platform_mode():
    db = AsyncMock()
    ctx = TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="u",
        is_superuser=False,
        permissions=frozenset({"marketplace:review"}),
    )
    with patch(
        "app.marketplace.review_config.get_marketplace_review_mode",
        new_callable=AsyncMock,
        return_value="platform",
    ):
        with pytest.raises(ForbiddenError, match="平台运营"):
            await require_tenant_review_allowed(db, ctx)


@pytest.mark.asyncio
async def test_admin_review_blocked_in_tenant_mode():
    db = AsyncMock()
    with patch(
        "app.marketplace.review_config.get_marketplace_review_mode",
        new_callable=AsyncMock,
        return_value="tenant",
    ):
        with pytest.raises(ForbiddenError, match="租户侧"):
            await require_platform_review_allowed(db)
