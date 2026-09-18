"""Redis 异步客户端工厂。"""

from __future__ import annotations

import asyncio

import redis.asyncio as aioredis

from miles_core.config import get_settings

_redis: aioredis.Redis | None = None
# 缓存所属的 loop **对象本身**，而非 ``id(loop)``：id 在旧 loop 被回收后可能被新 loop
# 复用，使「仍是同一个 loop」的判定误成立，把绑在已关闭 loop 上的客户端交出去。持有对象
# 既让判定精确（``is`` 不可能被地址复用欺骗），又顺带钉住旧 loop 使其地址不复用。
# 与 ``infra/db/async_session.py`` 的 ``_loop_engines`` 同理由，那处已写明该判据。
_redis_loop: asyncio.AbstractEventLoop | None = None


def get_redis() -> aioredis.Redis:
    """返回当前事件循环可用的 Redis 客户端。

    Celery Worker 每次 ``asyncio.run`` 都会新建 loop；若复用绑在旧 loop 上的
    连接，会触发 ``Future attached to a different loop``。
    """
    global _redis, _redis_loop
    try:
        loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if _redis is None or _redis_loop is not loop:
        settings = get_settings()
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        _redis_loop = loop
    return _redis


def reset_redis() -> None:
    """丢弃缓存客户端（Celery 任务结束、loop 关闭前调用）。"""
    global _redis, _redis_loop
    _redis = None
    _redis_loop = None
