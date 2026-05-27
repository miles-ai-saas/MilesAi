"""基础设施健康检查。

供 /health、MonitorService、SystemConfigService.runtime、/system/infra 调用；
components 键名兼容历史监控（weaviate/minio 别名）。
"""

import asyncio
import time
from typing import Literal

import httpx
from sqlalchemy import text

from app.core.config import get_settings
from app.infra.db import engine
from app.infra.redis import get_redis
from app.infra.storage import get_object_storage
from app.infra.vector_store import get_vector_store

settings = get_settings()

COMPONENT_IDS = ("postgres", "redis", "object_storage", "vector_store", "celery")

COMPONENT_LABELS: dict[str, str] = {
    "postgres": "PostgreSQL",
    "redis": "Redis",
    "object_storage": "对象存储 (MinIO/S3)",
    "vector_store": "向量库",
    "celery": "Celery Broker",
}

StatusValue = Literal["ok", "unavailable", "skipped"]


async def check_postgres() -> bool:
    """SELECT 1 探测异步引擎连通性。"""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def check_redis() -> bool:
    """PING 探测 Redis。"""
    try:
        return bool(await get_redis().ping())
    except Exception:
        return False


async def check_vector_store() -> bool:
    """委托当前 VECTOR_STORE_BACKEND 实现 health_check。"""
    try:
        return get_vector_store().health_check()
    except Exception:
        return False


async def check_object_storage() -> bool:
    """MinIO/S3 兼容存储桶探测。"""
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


async def check_celery_broker() -> bool:
    """PING Celery broker（通常为独立 Redis DB）。"""
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.celery_broker_url, decode_responses=True)
        try:
            return bool(await client.ping())
        finally:
            await client.aclose()
    except Exception:
        return False


async def probe_component(component_id: str) -> dict:
    """探测单个组件并返回结构化结果（含耗时）。"""
    if component_id not in COMPONENT_LABELS:
        return {
            "id": component_id,
            "label": component_id,
            "status": "skipped",
            "latency_ms": None,
            "message": "未知组件",
        }

    checkers = {
        "postgres": check_postgres,
        "redis": check_redis,
        "object_storage": check_object_storage,
        "vector_store": check_vector_store,
        "celery": check_celery_broker,
    }
    checker = checkers[component_id]
    started = time.perf_counter()
    ok = False
    message: str | None = None
    try:
        ok = await checker()
        if not ok:
            message = "连接失败"
    except Exception as exc:
        message = str(exc)[:200]

    latency_ms = int((time.perf_counter() - started) * 1000)
    return {
        "id": component_id,
        "label": COMPONENT_LABELS[component_id],
        "status": "ok" if ok else "unavailable",
        "latency_ms": latency_ms,
        "message": message,
    }


async def probe_components(component_ids: list[str] | None = None) -> list[dict]:
    """并行探测指定组件（默认全部）。"""
    ids = list(component_ids) if component_ids else list(COMPONENT_IDS)
    results = await asyncio.gather(*(probe_component(cid) for cid in ids))
    return list(results)


def build_infra_settings_preview() -> dict[str, str | None]:
    """部署级连接信息（脱敏，不含密码/完整 URL）。"""
    s = get_settings()
    backend = s.vector_store_backend.strip().lower()
    if backend == "weaviate":
        vector_endpoint = s.weaviate_url
    elif backend == "milvus":
        vector_endpoint = s.milvus_uri
    elif backend == "pgvector":
        vector_endpoint = f"{s.postgres_host}:{s.postgres_port}/{s.postgres_db}"
    else:
        vector_endpoint = backend

    return {
        "app_env": s.app_env,
        "postgres": f"{s.postgres_host}:{s.postgres_port}/{s.postgres_db}",
        "redis": f"{s.redis_host}:{s.redis_port}/{s.redis_db}",
        "object_storage_backend": s.object_storage_backend,
        "object_storage_endpoint": s.object_storage_endpoint,
        "object_storage_bucket": s.object_storage_bucket,
        "vector_store_backend": s.vector_store_backend,
        "vector_store_endpoint": vector_endpoint,
        "celery_broker": "***" if s.celery_broker_url else None,
        "embedding_backend": s.embedding_backend,
    }


async def collect_infra_status() -> dict:
    """聚合基础设施状态（含各组件耗时与脱敏配置预览）。"""
    components = await probe_components()
    healthy = all(c["status"] == "ok" for c in components)
    return {
        "healthy": healthy,
        "status": "healthy" if healthy else "degraded",
        "components": components,
        "settings_preview": build_infra_settings_preview(),
    }


async def collect_health_status() -> dict:
    """并行探测各组件，返回 {healthy, status, components}。"""
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
