"""基础设施健康检查。"""

import asyncio

import httpx
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine
from app.core.redis_client import get_redis

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


async def check_weaviate() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.weaviate_url}/v1/.well-known/ready")
            return r.status_code == 200
    except Exception:
        return False


async def check_minio() -> bool:
    try:
        scheme = "https" if settings.minio_secure else "http"
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{scheme}://{settings.minio_endpoint}/minio/health/live")
            return r.status_code == 200
    except Exception:
        return False


async def collect_health_status() -> dict:
    postgres, redis_ok, weaviate, minio = await asyncio.gather(
        check_postgres(),
        check_redis(),
        check_weaviate(),
        check_minio(),
    )
    components = {
        "postgres": postgres,
        "redis": redis_ok,
        "weaviate": weaviate,
        "minio": minio,
    }
    healthy = all(components.values())
    return {
        "healthy": healthy,
        "status": "healthy" if healthy else "degraded",
        "components": components,
    }
