"""A2A 对外端点的按 API Key 限流（维度的取值约定见 ``RateLimitScope``）。

为什么不在中间件里做：中间件跑在鉴权**之前**，只能从 Header 取 ``X-API-Key`` 当桶键 ——
任意伪造的 Key 都能造出桶键（缓存污染），且拿不到 JSON-RPC ``id``，超限只能回
``id: null``，对端无法把错误对回自己的请求。故检查点放在视图内、鉴权之后。
"""

from __future__ import annotations

from uuid import UUID

from miles_core.logging import get_logger
from miles_core.models.risk import RateLimitScope, RiskSeverity
from miles_core.risk.enforce import RateLimitHit, platform_risk_enforcer
from miles_core.tenant import TenantContext

logger = get_logger(__name__)


def client_bucket_key(ctx: TenantContext) -> str | None:
    """限流桶键：按 API Key 的**行 id**（不用明文/哈希 —— Redis 键不该承载凭证材料）。"""
    return f"key:{ctx.api_key_id}" if ctx.api_key_id else None


async def check_a2a_rate_limit(
    ctx: TenantContext,
    agent_id: UUID,
    *,
    path: str,
    ip: str | None,
) -> RateLimitHit | None:
    """返回命中的限流规则；放行返回 None。

    失败姿态是 **fail-open**：Redis/风控检查出错时放行并记日志。取舍明说 —— 平台对外
    端点因 Redis 抖动而全量 429/5xx，代价大于短时限流失效；限流是保护措施，不是正确性依赖。
    """
    client_key = client_bucket_key(ctx)
    if client_key is None:
        # 非 API Key 通道（JWT 调试）没有对端粒度可依，交回中间件按 IP 兜。
        return None
    try:
        hit = await platform_risk_enforcer.check_rate_limit(path, client_key, scope=RateLimitScope.API_KEY)
    except Exception:
        logger.exception("A2A 限流检查失败，放行本次请求: agent_id=%s", agent_id)
        return None
    if hit is None:
        return None
    # 事件写入单独 try：把两步并进一个 try 的话，写事件失败会被上层 except 吞成「放行」，
    # 而命中判定已经成立 —— 放行才是错的方向。
    try:
        await platform_risk_enforcer.record_event(
            event_type="a2a_rate_limit",
            severity=RiskSeverity.MEDIUM,
            ip_address=ip,
            tenant_id=ctx.tenant_id,
            detail={
                "kind": "a2a_rate_limit",
                "path": path,
                "agent_id": str(agent_id),
                "apiKeyId": str(ctx.api_key_id),
                "rule_id": str(hit.rule_id),
                "limit_per_minute": hit.limit_per_minute,
            },
        )
    except Exception:
        logger.exception("A2A 限流事件写入失败: agent_id=%s", agent_id)
    return hit
