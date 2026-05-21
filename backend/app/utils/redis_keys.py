"""Redis Key 命名规范，避免魔法字符串散落。"""

from uuid import UUID


class RedisKeys:
    @staticmethod
    def session(user_id: UUID | str) -> str:
        return f"session:{user_id}"

    @staticmethod
    def token_blacklist(jti: str) -> str:
        return f"token:blacklist:{jti}"

    @staticmethod
    def api_cache(namespace: str, key_hash: str) -> str:
        return f"cache:api:{namespace}:{key_hash}"

    @staticmethod
    def ingest_lock(file_id: UUID | str) -> str:
        return f"lock:ingest:{file_id}"

    @staticmethod
    def rate_limit(tenant_id: UUID | str, api: str) -> str:
        return f"ratelimit:{tenant_id}:{api}"

    @staticmethod
    def tenant_prefix(tenant_id: UUID | str) -> str:
        return f"t:{tenant_id}:"
