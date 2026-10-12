"""扫描各租户本月 Token 用量，达告警阈值则推送 Webhook/邮件（Redis 幂等）。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from miles_common.redis_keys import RedisKeys
from miles_core.infra.db import AsyncSessionLocal, run_worker_db_coro
from miles_core.infra.redis import get_redis, reset_redis
from miles_core.jobs.tasks import TASK_NAMES
from miles_core.logging import get_logger
from miles_core.models.platform.tenant import Tenant, TenantStatus
from miles_core.tenant import TenantContext
from miles_portal.tenant.monitor.services.monitor import MonitorService
from miles_worker.app import celery_app
from miles_worker.tasks.quota_reset import current_token_period_utc

logger = get_logger(__name__)

_SYSTEM_USER_ID = UUID(int=0)
_PERIOD_MARK_TTL_SEC = 40 * 24 * 3600


def _system_ctx(tenant_id: UUID) -> TenantContext:
    return TenantContext(
        user_id=_SYSTEM_USER_ID,
        tenant_id=tenant_id,
        username="system",
        is_superuser=True,
        permissions=frozenset(),
    )


async def check_tokens_monthly_threshold_async() -> str:
    """对活跃租户检查本月 Token 占比；达阈值且未告警过则通知。"""
    period = current_token_period_utc()
    redis = get_redis()
    alerted = 0
    skipped = 0
    scanned = 0

    async with AsyncSessionLocal() as db:
        tenants = list(
            (
                await db.execute(
                    select(Tenant).where(
                        Tenant.is_active.is_(True),
                        Tenant.status == TenantStatus.ACTIVE,
                        Tenant.max_tokens_monthly > 0,
                    )
                )
            ).scalars().all()
        )

        for tenant in tenants:
            scanned += 1
            limit = int(tenant.max_tokens_monthly)
            used = int(tenant.tokens_used_month)
            if limit <= 0:
                continue
            percent = min(100, int(used * 100 / limit))
            svc = MonitorService(db, _system_ctx(tenant.id))
            cfg = await svc.get_alert_config()
            if not cfg.enabled or not cfg.notify_on_tokens_monthly_threshold:
                continue
            warn = int(cfg.tokens_monthly_warn_percent)
            if percent < warn:
                continue
            mark_key = RedisKeys.tokens_threshold_alert(tenant.id, period, warn)
            if await redis.get(mark_key):
                skipped += 1
                continue
            await svc.notify_tokens_monthly_threshold(
                used=used,
                limit=limit,
                percent=percent,
                warn_percent=warn,
                cfg=cfg,
            )
            await redis.setex(mark_key, _PERIOD_MARK_TTL_SEC, "1")
            alerted += 1

    return f"scanned={scanned} alerted={alerted} skipped={skipped} period={period}"


@celery_app.task(name=TASK_NAMES["check_tokens_monthly_threshold"])
def check_tokens_monthly_threshold() -> str:
    """Beat：定期检查各租户本月 Token 是否达到告警阈值。"""
    try:
        return run_worker_db_coro(check_tokens_monthly_threshold_async())
    except Exception as exc:
        logger.error("check_tokens_monthly_threshold failed: %s", exc)
        raise
    finally:
        reset_redis()
