"""内置 ``redis_kv``：租户隔离的简易 KV（get/set/delete/exists/incr）。

护栏
----
- 键一律落在 ``agent_kv:{tenant_id}:…``，禁止访问平台其它 Redis 键。
- 相对 key 仅允许 ``[A-Za-z0-9._:/-]``，长度上限；禁止 ``..`` / 空白。
- 值长度上限；TTL 有上下限；不提供 KEYS/FLUSH/CONFIG 等危险命令。
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from miles_common.exceptions import BadRequestError
from miles_common.redis_keys import RedisKeys
from miles_core.infra.redis import get_redis

ALLOWED_OPS = frozenset({"get", "set", "delete", "exists", "incr"})
_KEY_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,128}$")
MAX_VALUE_CHARS = 64 * 1024
MIN_TTL_SEC = 1
MAX_TTL_SEC = 30 * 24 * 3600
DEFAULT_TTL_SEC = 24 * 3600


def normalize_relative_key(raw: object) -> str:
    """校验并规范化相对 key。"""
    if raw is None or not str(raw).strip():
        raise BadRequestError("redis_kv 需要 key")
    key = str(raw).strip()
    if ".." in key or key.startswith("/") or " " in key or "\n" in key:
        raise BadRequestError("redis_kv key 非法")
    if not _KEY_RE.match(key):
        raise BadRequestError("redis_kv key 仅允许字母数字与 ._:/ -，最长 128")
    return key


def resolve_full_key(tenant_id: UUID, relative_key: str) -> str:
    """租户隔离后的完整 Redis 键。"""
    return RedisKeys.agent_kv(tenant_id, relative_key)


def _parse_op(raw: object) -> str:
    op = str(raw or "").strip().lower()
    if op not in ALLOWED_OPS:
        raise BadRequestError(f"redis_kv op 须为其一: {', '.join(sorted(ALLOWED_OPS))}")
    return op


def _parse_ttl(raw: object) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        ttl = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise BadRequestError("ttl_sec 须为整数") from exc
    if ttl < MIN_TTL_SEC or ttl > MAX_TTL_SEC:
        raise BadRequestError(f"ttl_sec 范围 {MIN_TTL_SEC}–{MAX_TTL_SEC}")
    return ttl


async def run_redis_kv(tenant_id: UUID, params: dict) -> dict[str, Any]:
    """执行一次 KV 操作；返回结构化结果（不含其它租户信息）。"""
    op = _parse_op(params.get("op") or params.get("operation"))
    relative = normalize_relative_key(params.get("key"))
    full_key = resolve_full_key(tenant_id, relative)
    redis = get_redis()

    if op == "get":
        value = await redis.get(full_key)
        ttl = await redis.ttl(full_key)
        return {
            "op": op,
            "key": relative,
            "exists": value is not None,
            "value": value,
            "ttl_sec": ttl if isinstance(ttl, int) and ttl >= 0 else None,
        }

    if op == "exists":
        n = await redis.exists(full_key)
        return {"op": op, "key": relative, "exists": bool(n)}

    if op == "delete":
        removed = await redis.delete(full_key)
        return {"op": op, "key": relative, "deleted": bool(removed)}

    if op == "incr":
        try:
            amount = int(params.get("amount", 1))
        except (TypeError, ValueError) as exc:
            raise BadRequestError("amount 须为整数") from exc
        if abs(amount) > 1_000_000:
            raise BadRequestError("amount 过大")
        # incrby 要求值已是整数或键不存在
        try:
            new_val = await redis.incrby(full_key, amount)
        except Exception as exc:
            raise BadRequestError("incr 失败：键值须为整数或不存在") from exc
        ttl = _parse_ttl(params.get("ttl_sec"))
        if ttl is not None:
            await redis.expire(full_key, ttl)
        return {"op": op, "key": relative, "value": new_val}

    # set
    if "value" not in params:
        raise BadRequestError("set 需要 value")
    value = params.get("value")
    if value is None:
        value = ""
    if not isinstance(value, (str, int, float, bool)):
        raise BadRequestError("value 须为字符串或标量")
    text = value if isinstance(value, str) else str(value)
    if len(text) > MAX_VALUE_CHARS:
        raise BadRequestError(f"value 最长 {MAX_VALUE_CHARS} 字符")
    ttl = _parse_ttl(params.get("ttl_sec"))
    if ttl is None:
        ttl = DEFAULT_TTL_SEC
    await redis.set(full_key, text, ex=ttl)
    return {"op": "set", "key": relative, "ok": True, "ttl_sec": ttl}
