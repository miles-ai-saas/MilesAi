"""月初 Token 用量清零。"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from miles_worker.tasks.quota_reset import current_token_period_utc, reset_tokens_used_month_async


def test_current_token_period_utc():
    assert current_token_period_utc(datetime(2026, 10, 12, 8, 0, tzinfo=UTC)) == "2026-10"


@pytest.mark.asyncio
async def test_reset_skips_when_period_marked():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value="1")
    with patch("miles_worker.tasks.quota_reset.get_redis", return_value=redis):
        out = await reset_tokens_used_month_async(period="2026-10")
    assert out == "skipped period=2026-10"
    redis.setex.assert_not_called()


@pytest.mark.asyncio
async def test_reset_zeros_and_marks_period():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()

    result = MagicMock()
    result.rowcount = 3
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("miles_worker.tasks.quota_reset.get_redis", return_value=redis),
        patch("miles_worker.tasks.quota_reset.AsyncSessionLocal", return_value=cm),
    ):
        out = await reset_tokens_used_month_async(period="2026-11")

    assert out == "reset period=2026-11 rows=3"
    db.execute.assert_awaited()
    db.commit.assert_awaited()
    redis.setex.assert_awaited()
