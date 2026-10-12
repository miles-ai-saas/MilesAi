"""本月 Token 配额预检与用量累加。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from miles_common.exceptions import ForbiddenError
from miles_core.models.model import ModelConfig
from miles_portal.tenant.models.services.usage import UsageRecordContext, record_model_usage
from miles_portal.tenant.system.services.quota import assert_tokens_monthly


@pytest.mark.asyncio
async def test_assert_tokens_monthly_unlimited():
    tenant = SimpleNamespace(max_tokens_monthly=0, tokens_used_month=999_999)
    db = AsyncMock()
    db.get = AsyncMock(return_value=tenant)
    await assert_tokens_monthly(db, uuid4())


@pytest.mark.asyncio
async def test_assert_tokens_monthly_ok_under_limit():
    tenant = SimpleNamespace(max_tokens_monthly=1000, tokens_used_month=100)
    db = AsyncMock()
    db.get = AsyncMock(return_value=tenant)
    await assert_tokens_monthly(db, uuid4())


@pytest.mark.asyncio
async def test_assert_tokens_monthly_exceeded():
    tenant = SimpleNamespace(max_tokens_monthly=1000, tokens_used_month=1000)
    db = AsyncMock()
    db.get = AsyncMock(return_value=tenant)
    with pytest.raises(ForbiddenError, match="本月 Token"):
        await assert_tokens_monthly(db, uuid4())


@pytest.mark.asyncio
async def test_record_model_usage_bumps_tokens_used_month():
    db = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    model = ModelConfig(id=uuid4(), name="m", provider="openai", model_name="x")
    ctx = UsageRecordContext(db=db, tenant_id=uuid4(), model=model, source="flow")

    await record_model_usage(ctx, prompt_tokens=10, completion_tokens=5)

    db.execute.assert_awaited()
    db.add.assert_called_once()
    db.flush.assert_awaited()
