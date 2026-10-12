"""智能体级限流配置解析与 Redis 窗口。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from miles_common.exceptions import RateLimitError
from miles_portal.tenant.agents.services.agent_limits import (
    assert_agent_chat_limits,
    assert_agent_tool_limits,
    resolve_max_tool_iterations,
)


def test_resolve_max_tool_iterations_prefers_limits():
    assert resolve_max_tool_iterations({"limits": {"max_tool_iterations": 8}, "max_tool_iterations": 3}) == 8
    assert resolve_max_tool_iterations({"max_tool_iterations": 3}) == 3
    assert resolve_max_tool_iterations({}) == 5


@pytest.mark.asyncio
async def test_assert_chat_limits_noop_when_unlimited():
    agent = SimpleNamespace(id=uuid4(), config={})
    ctx = SimpleNamespace(user_id=uuid4(), tenant_id=uuid4())
    await assert_agent_chat_limits(agent, ctx)


@pytest.mark.asyncio
async def test_assert_chat_limits_blocks_when_over_rpm():
    agent = SimpleNamespace(id=uuid4(), config={"limits": {"chat_per_minute": 2}})
    ctx = SimpleNamespace(user_id=uuid4(), tenant_id=uuid4())
    redis = MagicMock()
    redis.incr = AsyncMock(return_value=3)
    redis.expire = AsyncMock()
    redis.ttl = AsyncMock(return_value=40)

    with patch("miles_portal.tenant.agents.services.agent_limits.get_redis", return_value=redis):
        with pytest.raises(RateLimitError, match="每分钟") as ei:
            await assert_agent_chat_limits(agent, ctx)
    assert ei.value.status_code == 429
    assert ei.value.retry_after == 40


@pytest.mark.asyncio
async def test_assert_tool_limits_blocks():
    redis = MagicMock()
    redis.incr = AsyncMock(return_value=5)
    redis.expire = AsyncMock()
    redis.ttl = AsyncMock(return_value=12)

    with patch("miles_portal.tenant.agents.services.agent_limits.get_redis", return_value=redis):
        with pytest.raises(RateLimitError, match="工具调用"):
            await assert_agent_tool_limits(
                agent_id=uuid4(),
                user_id=uuid4(),
                agent_config={"limits": {"tool_per_minute": 2}},
            )


@pytest.mark.asyncio
async def test_assert_tool_limits_fail_open_on_redis_error():
    with patch(
        "miles_portal.tenant.agents.services.agent_limits.get_redis",
        side_effect=RuntimeError("redis down"),
    ):
        await assert_agent_tool_limits(
            agent_id=uuid4(),
            user_id=uuid4(),
            agent_config={"limits": {"tool_per_minute": 1}},
        )
