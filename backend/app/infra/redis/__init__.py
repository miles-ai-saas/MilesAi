"""Redis 连接。"""

from app.infra.redis.client import get_redis, reset_redis

__all__ = ["get_redis", "reset_redis"]
