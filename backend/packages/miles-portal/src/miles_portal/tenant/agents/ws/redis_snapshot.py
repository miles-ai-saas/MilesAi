"""对话 WS 事件环缓的 Redis 镜像（跨 worker 断线续传）。

本地 ``SessionEventBuffer`` 仍为热路径；每次入缓后 RPUSH+LTRIM+EXPIRE。
新 worker 上本地无缓冲时从 Redis LRANGE 回填。Redis 不可用时静默失败（仍可用本机环缓）。
"""

from __future__ import annotations

import json
from typing import Any

from miles_common.redis_keys import RedisKeys
from miles_core.config import get_settings
from miles_core.logging import get_logger

logger = get_logger(__name__)


def _limits() -> tuple[int, int]:
    settings = get_settings()
    max_size = max(8, int(settings.agent_chat_ws_event_buffer_size))
    ttl = max(30, int(settings.agent_chat_ws_event_buffer_ttl_sec))
    return max_size, ttl


def redis_snapshot_enabled() -> bool:
    """是否启用跨 worker Redis 快照。"""
    return bool(get_settings().agent_chat_ws_redis_snapshot_enabled)


async def persist_event(session_key: str, envelope: dict[str, Any]) -> None:
    """将事件追加到 Redis LIST；失败只打日志。"""
    if not redis_snapshot_enabled() or not session_key:
        return
    try:
        from miles_core.infra.redis import get_redis

        redis = get_redis()
        key = RedisKeys.agent_chat_ws_events(session_key)
        max_size, ttl = _limits()
        pipe = redis.pipeline()
        pipe.rpush(key, json.dumps(envelope, ensure_ascii=False))
        pipe.ltrim(key, -max_size, -1)
        pipe.expire(key, ttl)
        await pipe.execute()
    except Exception:
        logger.debug("ws redis snapshot persist failed key=%s", session_key, exc_info=True)


async def load_events(session_key: str) -> list[dict[str, Any]]:
    """从 Redis 读取会话事件列表；失败返回空列表。"""
    if not redis_snapshot_enabled() or not session_key:
        return []
    try:
        from miles_core.infra.redis import get_redis

        redis = get_redis()
        key = RedisKeys.agent_chat_ws_events(session_key)
        raw_items = await redis.lrange(key, 0, -1)
    except Exception:
        logger.debug("ws redis snapshot load failed key=%s", session_key, exc_info=True)
        return []
    out: list[dict[str, Any]] = []
    for raw in raw_items or []:
        try:
            item = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(item, dict) and item.get("id"):
            out.append(item)
    return out
