"""平台风控运行时：IP 黑名单与 API 限流。"""

from __future__ import annotations

import fnmatch
import math
import time
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select

from miles_core.infra.db.async_session import AsyncSessionLocal
from miles_core.infra.redis import get_redis
from miles_core.models.risk import IpBlacklist, RateLimitRule, RateLimitScope, RiskEvent, RiskSeverity

_CACHE_TTL_SEC = 30.0


@dataclass(frozen=True)
class _RateRule:
    id: UUID
    path_pattern: str
    limit_per_minute: int
    scope: str


@dataclass(frozen=True)
class RateLimitHit:
    """命中的限流规则与恢复时间（调用方据此回 429 + ``Retry-After``）。"""

    rule_id: UUID
    limit_per_minute: int
    retry_after_seconds: int


class PlatformRiskEnforcer:
    """内存缓存 + Redis 滑动窗口限流。"""

    def __init__(self) -> None:
        self._loaded_at = 0.0
        self._blocked_ips: set[str] = set()
        self._rate_rules: list[_RateRule] = []

    def invalidate_cache(self) -> None:
        """使内存缓存立即失效，下次访问时重新从库加载。"""
        self._loaded_at = 0.0

    async def _ensure_cache(self) -> None:
        now = time.monotonic()
        if now - self._loaded_at < _CACHE_TTL_SEC:
            return
        async with AsyncSessionLocal() as db:
            ip_rows = list((await db.execute(select(IpBlacklist.ip_address).where(IpBlacklist.is_active.is_(True)))).scalars())
            rule_rows = list((await db.execute(select(RateLimitRule).where(RateLimitRule.is_active.is_(True)))).scalars())
        self._blocked_ips = {ip.strip() for ip in ip_rows if ip}
        self._rate_rules = [_RateRule(id=r.id, path_pattern=r.path_pattern, limit_per_minute=r.limit_per_minute, scope=r.scope) for r in rule_rows]
        self._loaded_at = now

    @staticmethod
    def _match_path(pattern: str, path: str) -> bool:
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return path.startswith(prefix) or fnmatch.fnmatch(path, pattern)
        return path == pattern or fnmatch.fnmatch(path, pattern)

    async def is_ip_blocked(self, ip: str) -> bool:
        """判断 IP 是否命中黑名单（基于内存缓存）。"""
        await self._ensure_cache()
        return ip in self._blocked_ips

    async def check_rate_limit(self, path: str, client_key: str, *, scope: RateLimitScope) -> RateLimitHit | None:
        """按 ``scope`` 维度检查固定窗口；超限返回命中信息，否则 None。

        ``scope`` 是**必填关键字**：调用方必须显式声明自己算哪个维度 —— 否则将来新增
        调用方时会默默继承一个错的语义，而这类错误在线上只表现为「限流不管用」。

        命中多规则时取首个超限者（沿用短路顺序），不累加。
        """
        await self._ensure_cache()
        now = time.time()
        bucket = int(now // 60)
        for rule in self._rate_rules:
            # 比 ``.value`` 而非枚举本身：``_RateRule.scope`` 是从库里读回的普通字符串，
            # 显式取值比较不依赖 StrEnum 的 str 子类相等性。
            if rule.scope != scope.value or not self._match_path(rule.path_pattern, path):
                continue
            redis = get_redis()
            key = f"ratelimit:{rule.id}:{client_key}:{bucket}"
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, 120)
            if count > rule.limit_per_minute:
                # 固定窗口剩余秒数，下限 1：回 0 等于让对端立刻重试，比不回更糟。
                return RateLimitHit(
                    rule_id=rule.id,
                    limit_per_minute=rule.limit_per_minute,
                    retry_after_seconds=max(1, math.ceil(bucket * 60 + 60 - now)),
                )
        return None

    async def record_event(
        self,
        *,
        event_type: str,
        severity: RiskSeverity,
        ip_address: str | None,
        detail: dict,
        tenant_id: UUID | None = None,
    ) -> None:
        """将风险事件写入独立会话，并自行 commit。"""
        async with AsyncSessionLocal() as db:
            db.add(
                RiskEvent(
                    event_type=event_type,
                    severity=severity,
                    tenant_id=tenant_id,
                    ip_address=ip_address,
                    detail=detail,
                )
            )
            await db.commit()


platform_risk_enforcer = PlatformRiskEnforcer()
