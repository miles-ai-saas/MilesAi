"""Redis 异步客户端工厂。"""

from functools import lru_cache

import redis.asyncio as aioredis

from app.core.config import get_settings


@lru_cache
def get_redis() -> aioredis.Redis:
    """进程内单例 Redis 客户端（decode_responses=True）。"""
    settings = get_settings()
    return aioredis.from_url(settings.redis_url, decode_responses=True)
