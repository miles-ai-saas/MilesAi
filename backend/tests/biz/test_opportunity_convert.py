"""商机 convert 与 pipeline 单元测试。"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.biz.services.opportunity import OpportunityService
from app.common.exceptions import BadRequestError
from app.core.tenant import TenantContext


@pytest.mark.asyncio
async def test_convert_to_project_requires_won_stage():
    tenant_id = uuid4()
    ctx = TenantContext(user_id=uuid4(), tenant_id=tenant_id, username="sales", is_superuser=True, permissions=frozenset())
    row = MagicMock()
    row.id = uuid4()
    row.tenant_id = tenant_id
    row.stage = "negotiation"
    row.converted_to_project_id = None

    svc = OpportunityService(AsyncMock(), ctx)
    svc._get_or_raise = AsyncMock(return_value=row)

    with pytest.raises(BadRequestError, match="赢单"):
        await svc.convert_to_project(row.id)


@pytest.mark.asyncio
async def test_convert_to_project_rejects_already_converted():
    tenant_id = uuid4()
    ctx = TenantContext(user_id=uuid4(), tenant_id=tenant_id, username="sales", is_superuser=True, permissions=frozenset())
    row = MagicMock()
    row.id = uuid4()
    row.tenant_id = tenant_id
    row.stage = "won"
    row.converted_to_project_id = uuid4()

    svc = OpportunityService(AsyncMock(), ctx)
    svc._get_or_raise = AsyncMock(return_value=row)

    with pytest.raises(BadRequestError, match="已转化"):
        await svc.convert_to_project(row.id)
