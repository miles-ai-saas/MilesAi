"""生成日配额。"""

from datetime import timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.common.exceptions import ForbiddenError
from app.integrations.generative.quota import (
    assert_generative_quota,
    get_generative_daily_limit,
)


@pytest.mark.asyncio
async def test_get_generative_daily_limit_unset():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    assert await get_generative_daily_limit(db) == 0


@pytest.mark.asyncio
async def test_assert_generative_quota_unlimited():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    await assert_generative_quota(db, uuid4(), units=10)


@pytest.mark.asyncio
async def test_assert_generative_quota_exceeded():
    tenant_id = uuid4()
    calls = {"n": 0}

    async def scalar(_stmt):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"value": 2}
        return 2

    db = AsyncMock()
    db.scalar = scalar
    with pytest.raises(ForbiddenError, match="今日生成次数"):
        await assert_generative_quota(db, tenant_id, units=1)


def test_utc_day_start_used_in_count_query():
    from app.integrations.generative import quota as mod

    start = mod._utc_day_start()
    assert start.tzinfo == timezone.utc
    assert start.hour == 0 and start.minute == 0
