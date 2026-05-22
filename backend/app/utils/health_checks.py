"""基础设施健康检查。"""

import asyncio

import httpx
from sqlalchemy import text

from app.core.config import get_settings
from app.infra.db import engine
from app.infra.redis import get_redis
from app.infra.storage import get_object_storage
from app.infra.vector_store import get_vector_store

settings = get_settings()


async def check_postgres() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def check_redis() -> bool:
    try:
        return bool(await get_redis().ping())
    except Exception:
        return False


async def check_vector_store() -> bool:
    try:
        return get_vector_store().health_check()
    except Exception:
        return False


async def check_object_storage() -> bool:
    try:
        return get_object_storage().health_check()
    except Exception:
        return False


async def check_weaviate() -> bool:
    """兼容：仅当后端为 weaviate 时检查 HTTP ready。"""
    if settings.vector_store_backend.strip().lower() != "weaviate":
        return True
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.weaviate_url}/v1/.well-known/ready")
            return r.status_code == 200
    except Exception:
        return False


async def check_minio() -> bool:
    """兼容别名 → object_storage。"""
    return await check_object_storage()


async def collect_health_status() -> dict:
    postgres, redis_ok, vector_store, object_storage = await asyncio.gather(
        check_postgres(),
        check_redis(),
        check_vector_store(),
        check_object_storage(),
    )
    components = {
        "postgres": postgres,
        "redis": redis_ok,
        "vector_store": vector_store,
        "object_storage": object_storage,
        # 兼容旧监控字段名
        "weaviate": vector_store if settings.vector_store_backend == "weaviate" else await check_weaviate(),
        "minio": object_storage,
    }
    healthy = all(
        [postgres, redis_ok, vector_store, object_storage]
    )
    return {
        "healthy": healthy,
        "status": "healthy" if healthy else "degraded",
        "components": components,
    }
