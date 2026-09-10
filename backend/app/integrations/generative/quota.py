"""
生成类 API 日配额（次数，非 KB 存储）。

配置键 ``generative.daily_limit_per_tenant``（system_config JSON，整数；0 或未配置表示不限）。
计数口径：当日 UTC 内 ``purpose ∈ {chat_generated, flow_generated}`` 的附件条数。
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import ForbiddenError
from app.core.soft_delete import not_deleted
from app.integrations.generative.constants import PURPOSE_CHAT_GENERATED, PURPOSE_FLOW_GENERATED
from app.models.media.attachment import Attachment
from app.models.platform.system import SystemConfig

_CONFIG_KEY = "generative.daily_limit_per_tenant"
_GENERATED_PURPOSES = (PURPOSE_CHAT_GENERATED, PURPOSE_FLOW_GENERATED)


def _config_int(raw: object, default: int = 0) -> int:
    if raw is None:
        return default
    if isinstance(raw, dict) and "value" in raw:
        raw = raw["value"]
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return default


def _utc_day_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def get_generative_daily_limit(db: AsyncSession) -> int:
    """租户每日生成次数上限；0 表示不限。"""
    row = await db.scalar(select(SystemConfig.value).where(SystemConfig.key == _CONFIG_KEY))
    return _config_int(row, 0)


async def count_generative_today(db: AsyncSession, tenant_id: UUID) -> int:
    """统计租户当日已落库的生成附件数。"""
    day_start = _utc_day_start()
    return int(
        await db.scalar(
            select(func.count())
            .select_from(Attachment)
            .where(
                Attachment.tenant_id == tenant_id,
                Attachment.purpose.in_(_GENERATED_PURPOSES),
                Attachment.created_at >= day_start,
                not_deleted(Attachment),
            )
        )
        or 0
    )


async def assert_generative_quota(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    units: int = 1,
) -> None:
    """调用厂商前校验：当日已用 + 本次 units 不得超过限额。"""
    limit = await get_generative_daily_limit(db)
    if limit <= 0:
        return
    units = max(1, int(units))
    used = await count_generative_today(db, tenant_id)
    if used + units > limit:
        raise ForbiddenError(f"今日生成次数已达上限（{used}/{limit}），请明日再试或联系管理员调整配额")
