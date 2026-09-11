"""多设备登录会话（Redis）与 JWT jti 黑名单。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from app.core.security import safe_decode_token
from app.infra.redis import get_redis
from app.utils.redis_keys import RedisKeys

SESSION_TTL_SECONDS = 60 * 60 * 24 * 7


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
    now = datetime.now(timezone.utc).isoformat()
    meta = {
        "jti": jti,
        "user_agent": (user_agent or "")[:512],
        "ip": ip or "",
        "created_at": now,
        "last_seen_at": now,
    }
    await redis.setex(_entry_key(user_id, jti), SESSION_TTL_SECONDS, json.dumps(meta))
    await redis.sadd(_index_key(user_id), jti)
    await redis.expire(_index_key(user_id), SESSION_TTL_SECONDS)


async def touch_session(user_id: UUID, jti: str) -> None:
    """请求通过鉴权时刷新 last_seen（轻量）。"""
    redis = await get_redis()
    raw = await redis.get(_entry_key(user_id, jti))
    if not raw:
        return
    try:
        meta = json.loads(raw)
    except json.JSONDecodeError:
        return
    meta["last_seen_at"] = datetime.now(timezone.utc).isoformat()
    ttl = await redis.ttl(_entry_key(user_id, jti))
    if ttl and ttl > 0:
        await redis.setex(_entry_key(user_id, jti), ttl, json.dumps(meta))


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
        ttl = max(60, int(exp - datetime.now(timezone.utc).timestamp()))
    redis = await get_redis()
    await redis.setex(RedisKeys.token_blacklist(jti), ttl, "1")


async def list_sessions(user_id: UUID) -> list[dict]:
    """列出用户会话元数据（按创建时间倒序），顺带清理索引中已失效的 jti。"""
    redis = await get_redis()
    jtis = await redis.smembers(_index_key(user_id))
    out: list[dict] = []
    for jti in sorted(jtis):
        raw = await redis.get(_entry_key(user_id, jti))
        if not raw:
            await redis.srem(_index_key(user_id), jti)
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    out.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return out


async def revoke_session(user_id: UUID, jti: str, *, access_token: str | None = None) -> None:
    """吊销单会话；传入 access_token 时按其原过期时间加黑名单。"""
    redis = await get_redis()
    if access_token:
        await blacklist_token(access_token)
    else:
        await redis.setex(RedisKeys.token_blacklist(jti), SESSION_TTL_SECONDS, "1")
    await redis.delete(_entry_key(user_id, jti))
    await redis.srem(_index_key(user_id), jti)


async def revoke_all_sessions(user_id: UUID, *, keep_jti: str | None = None) -> int:
    """吊销用户全部会话（可保留 keep_jti），逐个加入黑名单并返回吊销数。"""
    redis = await get_redis()
    jtis = await redis.smembers(_index_key(user_id))
    revoked = 0
    for jti in jtis:
        if keep_jti and jti == keep_jti:
            continue
        await redis.setex(RedisKeys.token_blacklist(jti), SESSION_TTL_SECONDS, "1")
        await redis.delete(_entry_key(user_id, jti))
        await redis.srem(_index_key(user_id), jti)
        revoked += 1
    return revoked
