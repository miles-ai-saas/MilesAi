"""A2A ``tasks/pushNotificationConfig/*`` 的 Redis 存储（任务级 webhook 配置）。"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from miles_common.redis_keys import RedisKeys
from miles_core.infra.redis import get_redis
from miles_core.logging import get_logger
from miles_core.url_security import validate_outbound_url

logger = get_logger(__name__)

#: 每任务最多 webhook 数（防滥用）。
MAX_CONFIGS_PER_TASK = 8

#: 配置 TTL（秒）：生成任务最长存活远小于此；过期即不再推送。
CONFIG_TTL_SEC = 7 * 24 * 3600


def _config_key(tenant_id: UUID | str, task_id: UUID | str) -> str:
    return RedisKeys.a2a_push_notification_configs(tenant_id, task_id)


def _normalize_auth(raw: object) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("authentication 须为对象")
    schemes = raw.get("schemes")
    if schemes is not None and not isinstance(schemes, list):
        raise ValueError("authentication.schemes 须为数组")
    out: dict[str, Any] = {}
    if isinstance(schemes, list):
        out["schemes"] = [str(s) for s in schemes]
    creds = raw.get("credentials")
    if creds is not None:
        out["credentials"] = str(creds)
    return out or None


def normalize_push_config(raw: dict[str, Any], *, config_id: str | None = None) -> dict[str, Any]:
    """校验并规范化 ``PushNotificationConfig``；返回可落 Redis 的 dict。"""
    url = validate_outbound_url(str(raw.get("url") or ""))
    cid = (config_id or raw.get("id") or "").strip() or str(uuid4())
    token = raw.get("token")
    cfg: dict[str, Any] = {"id": cid, "url": url}
    if token is not None and str(token).strip():
        cfg["token"] = str(token).strip()
    auth = _normalize_auth(raw.get("authentication"))
    if auth:
        cfg["authentication"] = auth
    return cfg


def to_task_push_config(task_id: str, cfg: dict[str, Any]) -> dict[str, Any]:
    """线格式 ``TaskPushNotificationConfig``。"""
    return {
        "taskId": task_id,
        "pushNotificationConfig": {
            k: cfg[k]
            for k in ("id", "url", "token", "authentication")
            if k in cfg and cfg[k] is not None
        },
    }


async def set_config(
    *,
    tenant_id: UUID,
    task_id: UUID,
    push_config: dict[str, Any],
) -> dict[str, Any]:
    """写入或覆盖一条配置；返回规范化后的 ``PushNotificationConfig``。"""
    cfg = normalize_push_config(push_config)
    redis = get_redis()
    key = _config_key(tenant_id, task_id)
    existing = await redis.hlen(key)
    if existing >= MAX_CONFIGS_PER_TASK and not await redis.hexists(key, cfg["id"]):
        raise ValueError(f"每任务最多 {MAX_CONFIGS_PER_TASK} 条推送配置")
    await redis.hset(key, cfg["id"], json.dumps(cfg, ensure_ascii=False))
    await redis.expire(key, CONFIG_TTL_SEC)
    return cfg


async def get_config(
    *,
    tenant_id: UUID,
    task_id: UUID,
    config_id: str | None,
) -> dict[str, Any] | None:
    """取一条配置；``config_id`` 为空时若仅一条则返回它，多条则 None（须指定 id）。"""
    redis = get_redis()
    key = _config_key(tenant_id, task_id)
    if config_id and config_id.strip():
        raw = await redis.hget(key, config_id.strip())
        return json.loads(raw) if raw else None
    all_raw = await redis.hgetall(key)
    if not all_raw:
        return None
    if len(all_raw) == 1:
        return json.loads(next(iter(all_raw.values())))
    return None


async def list_configs(*, tenant_id: UUID, task_id: UUID) -> list[dict[str, Any]]:
    """列出任务下全部推送配置。"""
    redis = get_redis()
    all_raw = await redis.hgetall(_config_key(tenant_id, task_id))
    out: list[dict[str, Any]] = []
    for raw in all_raw.values():
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            logger.debug("skip corrupt push config", exc_info=True)
    out.sort(key=lambda c: str(c.get("id") or ""))
    return out


async def delete_config(*, tenant_id: UUID, task_id: UUID, config_id: str) -> bool:
    """删除配置；不存在亦视为成功（幂等），返回是否删到了键。"""
    redis = get_redis()
    key = _config_key(tenant_id, task_id)
    removed = await redis.hdel(key, config_id.strip())
    if await redis.hlen(key) == 0:
        await redis.delete(key)
    return bool(removed)
