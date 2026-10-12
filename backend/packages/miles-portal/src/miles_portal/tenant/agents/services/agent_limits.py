"""智能体级对话限流与工具调用配额（``config.limits``）。

配置示例::

    {
      "limits": {
        "chat_per_minute": 30,
        "chat_per_day": 500,
        "tool_per_minute": 60,
        "max_tool_iterations": 8
      },
      "max_tool_iterations": 8
    }

``0`` / 缺省表示不限。Redis 不可用时 **fail-open**（与 A2A 限流一致）。
``max_tool_iterations`` 可写在 ``limits`` 或根 config（后者兼容既有键）。
"""

from __future__ import annotations

import math
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from miles_common.exceptions import RateLimitError
from miles_core.infra.redis import get_redis
from miles_core.logging import get_logger
from miles_core.models.agent import Agent
from miles_core.tenant import TenantContext

logger = get_logger(__name__)


def _limits_cfg(agent_or_config: Agent | dict | None) -> dict:
    if agent_or_config is None:
        return {}
    if isinstance(agent_or_config, dict):
        cfg = agent_or_config
    else:
        cfg = agent_or_config.config if isinstance(agent_or_config.config, dict) else {}
    raw = cfg.get("limits")
    return raw if isinstance(raw, dict) else {}


def _positive_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def agent_chat_per_minute(agent: Agent) -> int:
    return _positive_int(_limits_cfg(agent).get("chat_per_minute"))


def agent_chat_per_day(agent: Agent) -> int:
    return _positive_int(_limits_cfg(agent).get("chat_per_day"))


def agent_tool_per_minute(config: dict | None) -> int:
    return _positive_int(_limits_cfg(config).get("tool_per_minute"))


def resolve_max_tool_iterations(config: dict | None, *, default: int = 5) -> int:
    """优先 ``limits.max_tool_iterations``，否则根 ``max_tool_iterations``。"""
    limits = _limits_cfg(config)
    if limits.get("max_tool_iterations") is not None:
        n = _positive_int(limits.get("max_tool_iterations"))
        return n if n > 0 else default
    cfg = config if isinstance(config, dict) else {}
    if cfg.get("max_tool_iterations") is not None:
        n = _positive_int(cfg.get("max_tool_iterations"))
        return n if n > 0 else default
    return default


async def _incr_fixed_window(key: str, *, limit: int, window_sec: int) -> tuple[bool, int]:
    """返回 ``(allowed, retry_after_seconds)``。limit<=0 视为不限。"""
    if limit <= 0:
        return True, 0
    try:
        redis = get_redis()
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_sec + 5)
        if count > limit:
            ttl = await redis.ttl(key)
            retry = ttl if ttl and ttl > 0 else window_sec
            return False, max(1, int(retry))
        return True, 0
    except Exception:
        logger.exception("agent limit redis failed key=%s，放行", key)
        return True, 0


async def assert_agent_chat_limits(agent: Agent, ctx: TenantContext) -> None:
    """对话入口限流：按用户 + 智能体分钟/日窗口。"""
    rpm = agent_chat_per_minute(agent)
    rpd = agent_chat_per_day(agent)
    if rpm <= 0 and rpd <= 0:
        return
    uid = ctx.user_id
    aid = agent.id
    now = time.time()
    if rpm > 0:
        bucket = int(now // 60)
        key = f"agent_limit:chat_m:{aid}:{uid}:{bucket}"
        ok, retry = await _incr_fixed_window(key, limit=rpm, window_sec=60)
        if not ok:
            raise RateLimitError(
                f"该智能体每分钟对话次数已达上限（{rpm}），请 {retry} 秒后重试",
                retry_after=retry,
            )
    if rpd > 0:
        day = datetime.now(UTC).strftime("%Y%m%d")
        key = f"agent_limit:chat_d:{aid}:{uid}:{day}"
        # 日窗 TTL：到次日 UTC 0 点的秒数 + 缓冲
        now_dt = datetime.now(UTC)
        tomorrow = (now_dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()) + 86400
        window = max(60, int(math.ceil(tomorrow - now)))
        ok, retry = await _incr_fixed_window(key, limit=rpd, window_sec=window)
        if not ok:
            raise RateLimitError(
                f"该智能体今日对话次数已达上限（{rpd}），请明日再试",
                retry_after=retry,
            )


async def assert_agent_tool_limits(
    *,
    agent_id: UUID,
    user_id: UUID,
    agent_config: dict | None,
) -> None:
    """工具执行前限流：按用户 + 智能体分钟窗口。"""
    rpm = agent_tool_per_minute(agent_config)
    if rpm <= 0:
        return
    bucket = int(time.time() // 60)
    key = f"agent_limit:tool_m:{agent_id}:{user_id}:{bucket}"
    ok, retry = await _incr_fixed_window(key, limit=rpm, window_sec=60)
    if not ok:
        raise RateLimitError(
            f"该智能体每分钟工具调用次数已达上限（{rpm}），请 {retry} 秒后重试",
            retry_after=retry,
        )
