"""基础设施健康检查。

供 /health、MonitorService、SystemConfigService.runtime、/system/infra 调用。
"""

import asyncio
import time
from typing import Literal

from sqlalchemy import text

from miles_core.config import get_settings
from miles_core.infra.db import engine
from miles_core.infra.redis import get_redis
from miles_core.infra.storage import get_object_storage
from miles_core.infra.vector_store import get_vector_store

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
        return await asyncio.to_thread(get_vector_store().health_check)
    except Exception:
        return False


async def check_object_storage() -> bool:
    """MinIO/S3 兼容存储桶探测。"""
    try:
        return await asyncio.to_thread(get_object_storage().health_check)
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


def _collect_worker_info_sync() -> dict:
    from miles_core.jobs.celery_app import celery_app

    inspect = celery_app.control.inspect()
    stats = inspect.stats() or {}
    active = inspect.active() or {}
    reserved = inspect.reserved() or {}
    active_queues = inspect.active_queues() or {}
    scheduled = inspect.scheduled() or {}

    workers = []
    total_active = 0
    total_reserved = 0
    for name in sorted(set(list(stats.keys()) + list(active.keys()))):
        w_stat = stats.get(name, {})
        w_active = active.get(name, [])
        w_reserved = reserved.get(name, [])
        w_queues = active_queues.get(name, [])
        pool = w_stat.get("pool", {})
        workers.append(
            {
                "name": name,
                "pool_size": pool.get("max-concurrency", 0) if isinstance(pool, dict) else 0,
                "active_tasks": len(w_active),
                "reserved_tasks": len(w_reserved),
                "queues": [q.get("name", "") for q in w_queues] if w_queues else [],
            }
        )
        total_active += len(w_active)
        total_reserved += len(w_reserved)

    return {
        "worker_count": len(workers),
        "workers": workers,
        "total_active_tasks": total_active,
        "total_reserved_tasks": total_reserved,
        "total_scheduled": sum(len(scheduled.get(w, [])) for w in scheduled),
    }


async def get_worker_info() -> dict:
    """获取 Celery Worker 状态（活跃数、队列、任务统计）。"""
    try:
        return await asyncio.to_thread(_collect_worker_info_sync)
    except Exception as exc:
        return {"error": str(exc)}


async def get_redis_info() -> dict:
    """获取 Redis INFO 统计（内存、命中率、连接数等）。"""
    try:
        redis_client = get_redis()
        info = await redis_client.info()
        hits = info.get("keyspace_hits", 0) or 0
        misses = info.get("keyspace_misses", 0) or 0
        total = hits + misses
        return {
            "used_memory_human": info.get("used_memory_human", "N/A"),
            "used_memory_peak_human": info.get("used_memory_peak_human", "N/A"),
            "connected_clients": info.get("connected_clients", 0),
            "keyspace_hits": hits,
            "keyspace_misses": misses,
            "hit_rate": round(hits / total * 100, 1) if total > 0 else 0,
            "uptime_in_seconds": info.get("uptime_in_seconds", 0),
            "redis_version": info.get("redis_version", "N/A"),
        }
    except Exception as exc:
        return {"error": str(exc)}


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


_CORE_HEALTH_IDS = ("postgres", "redis", "vector_store", "object_storage")


async def collect_health_status() -> dict:
    """并行探测各组件，返回 {healthy, status, components}。"""
    probed = await probe_components(list(_CORE_HEALTH_IDS))
    components = {item["id"]: item["status"] == "ok" for item in probed}
    healthy = all(components.values())
    return {
        "healthy": healthy,
        "status": "healthy" if healthy else "degraded",
        "components": components,
    }
