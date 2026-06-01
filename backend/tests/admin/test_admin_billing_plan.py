"""运营后台 Phase 4 计费与套餐测试。"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.common.exceptions import BadRequestError
from app.admin.app_ops.services.tenant import AdminTenantService
from app.models.platform.tenant import Tenant


@pytest.mark.asyncio
async def test_apply_inactive_plan_rejected():
    plan_id = uuid4()
    plan = MagicMock()
    plan.id = plan_id
    plan.is_active = False

    tenant = Tenant(id=uuid4(), name="t", is_active=True)
    svc = AdminTenantService(db=AsyncMock())
    svc.plans = AsyncMock()
    svc.plans.get_by_id = AsyncMock(return_value=plan)

    with pytest.raises(BadRequestError, match="停用"):
        await svc._apply_plan(tenant, plan_id)
