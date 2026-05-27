"""系统管理 Phase 1 单元测试。"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.common.exceptions import ForbiddenError
from app.models.tenant import Tenant
from app.tenant.system.services.quota import assert_can_create_agent, assert_can_create_flow


@pytest.mark.asyncio
async def test_assert_can_create_agent_raises_when_at_limit():
    tenant_id = uuid4()
    tenant = Tenant(id=tenant_id, name="t", max_agents=1, max_flows=5)
    db = AsyncMock()
    db.get = AsyncMock(return_value=tenant)

    with patch(
        "app.tenant.system.services.quota.count_agents",
        new_callable=AsyncMock,
        return_value=1,
    ):
        with pytest.raises(ForbiddenError, match="智能体数量已达上限"):
            await assert_can_create_agent(db, tenant_id)


@pytest.mark.asyncio
async def test_assert_can_create_flow_raises_when_at_limit():
    tenant_id = uuid4()
    tenant = Tenant(id=tenant_id, name="t", max_agents=10, max_flows=2)
    db = AsyncMock()
    db.get = AsyncMock(return_value=tenant)

    with patch(
        "app.tenant.system.services.quota.count_flows",
        new_callable=AsyncMock,
        return_value=2,
    ):
        with pytest.raises(ForbiddenError, match="流程数量已达上限"):
            await assert_can_create_flow(db, tenant_id)


def test_user_reset_password_schema_min_length():
    from pydantic import ValidationError

    from app.tenant.system.schemas.user import UserBatchDeactivate, UserResetPassword

    with pytest.raises(ValidationError):
        UserResetPassword(password="12345")
    assert UserResetPassword(password="123456").password == "123456"

    with pytest.raises(ValidationError):
        UserBatchDeactivate(user_ids=[])


@pytest.mark.asyncio
async def test_export_logs_csv_includes_header():
    from uuid import uuid4
    from datetime import datetime, timezone

    from app.core.tenant import TenantContext
    from app.tenant.audit_log.models import TenantAuditLog
    from app.tenant.audit_log.services.audit_log import TenantAuditLogService

    tenant_id = uuid4()
    ctx = TenantContext(
        tenant_id=tenant_id,
        user_id=uuid4(),
        username="tester",
        is_superuser=False,
        permissions=frozenset({"audit:read"}),
    )
    row = TenantAuditLog(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=uuid4(),
        action="auth.login",
        resource_type="user",
        resource_id=str(uuid4()),
        ip_address="127.0.0.1",
        user_agent="test",
        detail={},
        created_at=datetime.now(timezone.utc),
    )
    svc = TenantAuditLogService(AsyncMock(), ctx)
    svc.repo = AsyncMock()
    svc.repo.list_for_export = AsyncMock(return_value=[row])

    csv_text = await svc.export_logs_csv()
    assert csv_text.startswith("created_at,action,")
    assert "auth.login" in csv_text
