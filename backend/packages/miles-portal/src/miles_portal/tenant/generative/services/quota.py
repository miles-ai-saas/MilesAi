"""
生成类 API 日配额（次数，非 KB 存储）——L1 租户策略。

配置键 ``generative.daily_limit_per_tenant``（system_config JSON，整数；0 或未配置表示不限）。
计数口径：当日 UTC 内 ``purpose ∈ {chat_generated, flow_generated}`` 的附件条数。
``PURPOSE_*`` 常量取自 L3 中立常量模块 ``integrations.generative.constants``；
消费方：``tenant.generative.services.orchestration``（生成前校验）与
``tenant.system.services.quota``（配额页汇总）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_ai.integrations.generative.constants import PURPOSE_CHAT_GENERATED, PURPOSE_FLOW_GENERATED
from miles_common.exceptions import ForbiddenError
from miles_core.models.media.attachment import Attachment
from miles_core.models.platform.system import SystemConfig
from miles_core.soft_delete import not_deleted
from miles_core.utils.config_value import system_config_int

_CONFIG_KEY = "generative.daily_limit_per_tenant"
_GENERATED_PURPOSES = (PURPOSE_CHAT_GENERATED, PURPOSE_FLOW_GENERATED)


def _utc_day_start() -> datetime:
    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def get_generative_daily_limit(db: AsyncSession) -> int:
    """租户每日生成次数上限；0 表示不限。

    0 同时是「未配置」与「配置值非法」的回落值：本模块以「未配置即不限」为准，
    解析失败只记 warning（见 ``system_config_int``），不改变放行行为。
    """
    row = await db.scalar(select(SystemConfig.value).where(SystemConfig.key == _CONFIG_KEY))
    return system_config_int(row, default=0, minimum=0)


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
