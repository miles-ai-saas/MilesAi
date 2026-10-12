"""月初清零各租户 ``tokens_used_month``（UTC 账期，Redis 幂等）。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import update

from miles_common.redis_keys import RedisKeys
from miles_core.infra.db import AsyncSessionLocal, run_worker_db_coro
from miles_core.infra.redis import get_redis, reset_redis
from miles_core.jobs.tasks import TASK_NAMES
from miles_core.logging import get_logger
from miles_core.models.platform.tenant import Tenant
from miles_worker.app import celery_app

logger = get_logger(__name__)

# 标记保留约 40 天，覆盖跨月重复调度窗口。
_PERIOD_MARK_TTL_SEC = 40 * 24 * 3600


def current_token_period_utc(now: datetime | None = None) -> str:
    """UTC 账期键 ``YYYY-MM``。"""
    ts = now or datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    else:
        ts = ts.astimezone(UTC)
    return ts.strftime("%Y-%m")


async def reset_tokens_used_month_async(*, period: str | None = None, force: bool = False) -> str:
    """清零所有租户本月 Token 用量；同账期默认只执行一次。

    ``force=True`` 跳过 Redis 幂等（测试/运维手动补跑）。
    """
    period_key = period or current_token_period_utc()
    redis = get_redis()
    mark_key = RedisKeys.tokens_month_reset(period_key)
    if not force and await redis.get(mark_key):
        return f"skipped period={period_key}"

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(Tenant).where(Tenant.tokens_used_month != 0).values(tokens_used_month=0)
        )
        await db.commit()
        rows = int(result.rowcount or 0)

    await redis.setex(mark_key, _PERIOD_MARK_TTL_SEC, "1")
    return f"reset period={period_key} rows={rows}"


@celery_app.task(name=TASK_NAMES["reset_tokens_used_month"])
def reset_tokens_used_month() -> str:
    """Beat：每日 UTC 检查；新账期首次跑清零 ``sys_tenants.tokens_used_month``。"""
    try:
        return run_worker_db_coro(reset_tokens_used_month_async())
    except Exception as exc:
        logger.error("reset_tokens_used_month failed: %s", exc)
        raise
    finally:
        reset_redis()
