"""Redis 异步客户端工厂。"""

from __future__ import annotations

import asyncio

import redis.asyncio as aioredis

from app.core.config import get_settings

_redis: aioredis.Redis | None = None
_redis_loop_id: int | None = None


def get_redis() -> aioredis.Redis:
    """返回当前事件循环可用的 Redis 客户端。

    Celery Worker 每次 ``asyncio.run`` 都会新建 loop；若复用绑在旧 loop 上的
    连接，会触发 ``Future attached to a different loop``。
    """
    global _redis, _redis_loop_id
    try:
        loop_id = id(asyncio.get_running_loop())
    except RuntimeError:
        loop_id = None

    if _redis is None or _redis_loop_id != loop_id:
        settings = get_settings()
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        _redis_loop_id = loop_id
    return _redis


def reset_redis() -> None:
    """丢弃缓存客户端（Celery 任务结束、loop 关闭前调用）。"""
    global _redis, _redis_loop_id
    _redis = None
    _redis_loop_id = None
