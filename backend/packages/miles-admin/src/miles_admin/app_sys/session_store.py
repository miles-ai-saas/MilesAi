"""运营后台会话校验（Redis jti）。"""

from uuid import UUID

from miles_core.infra.redis import get_redis
from miles_common.redis_keys import RedisKeys


async def validate_admin_session(admin_id: UUID, jti: str | None) -> bool:
    """校验 access token 的 jti 与 Redis 中活跃会话一致。"""
    if not jti:
        return False
    stored = await get_redis().get(RedisKeys.admin_session(admin_id))
    if stored is None:
        return False
    stored_jti = stored.decode() if isinstance(stored, bytes) else str(stored)
    return stored_jti == jti


async def revoke_admin_session(admin_id: UUID) -> None:
    """删除管理员 Redis 会话键，使其 token 立即失效。"""
    await get_redis().delete(RedisKeys.admin_session(admin_id))
