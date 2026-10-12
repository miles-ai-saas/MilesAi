"""告警配置按租户隔离键读写。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from miles_portal.tenant.monitor.schemas.monitor import AlertConfig
from miles_portal.tenant.monitor.services.monitor import ALERT_CONFIG_KEY, MonitorService, alert_config_key


@pytest.mark.asyncio
async def test_save_uses_tenant_scoped_key():
    tenant_id = uuid4()
    ctx = SimpleNamespace(tenant_id=tenant_id)
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    db.add = MagicMock()
    db.flush = AsyncMock()
    svc = MonitorService(db, ctx)  # type: ignore[arg-type]

    body = AlertConfig(enabled=True, webhook_url="https://example.com", tokens_monthly_warn_percent=90)
    await svc.save_alert_config(body)

    row = db.add.call_args[0][0]
    assert row.key == alert_config_key(tenant_id)
    assert row.key.startswith(ALERT_CONFIG_KEY + ":")
    assert row.value["tokens_monthly_warn_percent"] == 90
