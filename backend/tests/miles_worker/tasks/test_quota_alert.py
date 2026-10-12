"""本月 Token 阈值告警扫描。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from miles_core.models.platform.tenant import TenantStatus
from miles_worker.tasks.quota_alert import check_tokens_monthly_threshold_async


@pytest.mark.asyncio
async def test_threshold_alert_fires_once():
    tenant_id = uuid4()
    tenant = SimpleNamespace(
        id=tenant_id,
        is_active=True,
        status=TenantStatus.ACTIVE,
        max_tokens_monthly=1000,
        tokens_used_month=850,
    )
    cfg = SimpleNamespace(
        enabled=True,
        notify_on_tokens_monthly_threshold=True,
        tokens_monthly_warn_percent=80,
        webhook_url="https://hook.example",
        email_notify_to="",
    )

    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()

    result = MagicMock()
    result.scalars.return_value.all.return_value = [tenant]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)

    svc = MagicMock()
    svc.get_alert_config = AsyncMock(return_value=cfg)
    svc.notify_tokens_monthly_threshold = AsyncMock()

    with (
        patch("miles_worker.tasks.quota_alert.get_redis", return_value=redis),
        patch("miles_worker.tasks.quota_alert.AsyncSessionLocal", return_value=cm),
        patch("miles_worker.tasks.quota_alert.MonitorService", return_value=svc),
        patch("miles_worker.tasks.quota_alert.current_token_period_utc", return_value="2026-10"),
    ):
        out = await check_tokens_monthly_threshold_async()

    assert "alerted=1" in out
    svc.notify_tokens_monthly_threshold.assert_awaited_once()
    redis.setex.assert_awaited()


@pytest.mark.asyncio
async def test_threshold_skips_when_already_marked():
    tenant = SimpleNamespace(
        id=uuid4(),
        is_active=True,
        status=TenantStatus.ACTIVE,
        max_tokens_monthly=1000,
        tokens_used_month=900,
    )
    cfg = SimpleNamespace(
        enabled=True,
        notify_on_tokens_monthly_threshold=True,
        tokens_monthly_warn_percent=80,
        webhook_url="https://hook.example",
        email_notify_to="",
    )
    redis = AsyncMock()
    redis.get = AsyncMock(return_value="1")

    result = MagicMock()
    result.scalars.return_value.all.return_value = [tenant]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)

    svc = MagicMock()
    svc.get_alert_config = AsyncMock(return_value=cfg)
    svc.notify_tokens_monthly_threshold = AsyncMock()

    with (
        patch("miles_worker.tasks.quota_alert.get_redis", return_value=redis),
        patch("miles_worker.tasks.quota_alert.AsyncSessionLocal", return_value=cm),
        patch("miles_worker.tasks.quota_alert.MonitorService", return_value=svc),
        patch("miles_worker.tasks.quota_alert.current_token_period_utc", return_value="2026-10"),
    ):
        out = await check_tokens_monthly_threshold_async()

    assert "skipped=1" in out
    svc.notify_tokens_monthly_threshold.assert_not_called()
