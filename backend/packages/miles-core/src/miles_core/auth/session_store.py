"""多设备登录会话（Redis）与 JWT jti 黑名单。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from miles_common.redis_keys import RedisKeys
from miles_core.infra.redis import get_redis
from miles_core.security import safe_decode_token

SESSION_TTL_SECONDS = 60 * 60 * 24 * 7
TOUCH_INTERVAL_SECONDS = 300  # 5 分钟内不重复刷新 last_seen


def _entry_key(user_id: UUID | str, jti: str) -> str:
    return RedisKeys.user_session_entry(user_id, jti)


def _index_key(user_id: UUID | str) -> str:
    return RedisKeys.user_session_index(user_id)


async def register_session(
    user_id: UUID,
    access_token: str,
    *,
    user_agent: str | None = None,
    ip: str | None = None,
) -> None:
    """登录/刷新后登记 access 令牌会话。"""
    payload = safe_decode_token(access_token)
    if not payload:
        return
    jti = payload.get("jti")
    if not jti:
        return
    redis = await get_redis()
    now = datetime.now(UTC).isoformat()
    meta = {
        "jti": jti,
        "user_agent": (user_agent or "")[:512],
        "ip": ip or "",
        "created_at": now,
        "last_seen_at": now,
    }
    index_key = _index_key(user_id)
    pipe = redis.pipeline(transaction=False)
    pipe.setex(_entry_key(user_id, jti), SESSION_TTL_SECONDS, json.dumps(meta))
    pipe.sadd(index_key, jti)
    pipe.expire(index_key, SESSION_TTL_SECONDS)
    await pipe.execute()


async def touch_session(
    user_id: UUID,
    jti: str,
    *,
    now: datetime | None = None,
) -> bool:
    """请求通过鉴权时刷新 last_seen；默认 5 分钟内节流，避免每请求 SETEX。"""
    redis = await get_redis()
    raw = await redis.get(_entry_key(user_id, jti))
    if not raw:
        return False
    try:
        meta = json.loads(raw)
    except json.JSONDecodeError:
        return False

    current = now or datetime.now(UTC)
    last_raw = meta.get("last_seen_at")
    if last_raw:
        try:
            last = datetime.fromisoformat(last_raw)
            if last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            if (current - last).total_seconds() < TOUCH_INTERVAL_SECONDS:
                return False
        except ValueError:
            pass

    meta["last_seen_at"] = current.isoformat()
    ttl = await redis.ttl(_entry_key(user_id, jti))
    if ttl and ttl > 0:
        await redis.setex(_entry_key(user_id, jti), ttl, json.dumps(meta))
        return True
    return False


async def is_token_blacklisted(jti: str) -> bool:
    """判断 jti 是否在 Redis 黑名单中（空 jti 恒为 False）。"""
    if not jti:
        return False
    redis = await get_redis()
    return bool(await redis.exists(RedisKeys.token_blacklist(jti)))


async def blacklist_token(access_token: str) -> None:
    """将 access jti 加入黑名单直至原令牌过期。"""
    payload = safe_decode_token(access_token)
    if not payload:
        return
    jti = payload.get("jti")
    if not jti:
        return
    exp = payload.get("exp")
    ttl = SESSION_TTL_SECONDS
    if isinstance(exp, (int, float)):
        ttl = max(60, int(exp - datetime.now(UTC).timestamp()))
    redis = await get_redis()
    await redis.setex(RedisKeys.token_blacklist(jti), ttl, "1")


async def list_sessions(user_id: UUID) -> list[dict]:
    """列出用户会话元数据（按创建时间倒序），顺带清理索引中已失效的 jti。"""
    redis = await get_redis()
    index_key = _index_key(user_id)
    jtis = list(await redis.smembers(index_key))
    if not jtis:
        return []

    keys = [_entry_key(user_id, jti) for jti in jtis]
    raws = await redis.mget(keys)

    out: list[dict] = []
    stale: list[str] = []
    for jti, raw in zip(jtis, raws, strict=True):
        if not raw:
            stale.append(jti)
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            # 静默可接受：会话元数据已损坏；跳过该 jti（与 touch_session 一致，用户重新登录即可）。
            stale.append(jti)
            continue

    if stale:
        pipe = redis.pipeline(transaction=False)
        for jti in stale:
            pipe.srem(index_key, jti)
        await pipe.execute()

    out.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return out


async def revoke_session(user_id: UUID, jti: str, *, access_token: str | None = None) -> None:
    """吊销单会话；传入 access_token 时按其原过期时间加黑名单。"""
    redis = await get_redis()
    pipe = redis.pipeline(transaction=False)
    if access_token:
        await blacklist_token(access_token)
    else:
        pipe.setex(RedisKeys.token_blacklist(jti), SESSION_TTL_SECONDS, "1")
    pipe.delete(_entry_key(user_id, jti))
    pipe.srem(_index_key(user_id), jti)
    await pipe.execute()


async def revoke_all_sessions(user_id: UUID, *, keep_jti: str | None = None) -> int:
    """吊销用户全部会话（可保留 keep_jti），pipeline 批量加黑名单并返回吊销数。"""
    redis = await get_redis()
    index_key = _index_key(user_id)
    jtis = await redis.smembers(index_key)
    targets = [jti for jti in jtis if not (keep_jti and jti == keep_jti)]
    if not targets:
        return 0

    pipe = redis.pipeline(transaction=False)
    for jti in targets:
        pipe.setex(RedisKeys.token_blacklist(jti), SESSION_TTL_SECONDS, "1")
        pipe.delete(_entry_key(user_id, jti))
        pipe.srem(index_key, jti)
    await pipe.execute()
    return len(targets)
