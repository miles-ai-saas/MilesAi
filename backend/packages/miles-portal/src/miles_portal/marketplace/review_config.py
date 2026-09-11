"""应用市场审核模式配置（SaaS platform / 私有化 tenant / off）。"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import ForbiddenError
from miles_core.config import get_settings
from miles_core.tenant import TenantContext
from miles_core.models.platform.system import SystemConfig

ReviewMode = Literal["platform", "tenant", "off"]
VALID_REVIEW_MODES = frozenset({"platform", "tenant", "off"})
CONFIG_KEY_MODE = "marketplace.review_mode"
CONFIG_KEY_TENANT = "marketplace.review_tenant_id"


def normalize_review_mode(raw: str | None) -> ReviewMode:
    """归一化审核模式；空值或非法值回退 ``platform``。"""
    if not raw:
        return "platform"
    mode = raw.strip().lower()
    if mode not in VALID_REVIEW_MODES:
        return "platform"
    return mode  # type: ignore[return-value]


def _config_scalar(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        if "value" in value:
            return str(value["value"])
        if "mode" in value:
            return str(value["mode"])
    return str(value)


async def get_marketplace_review_mode(db: AsyncSession | None = None) -> ReviewMode:
    """读取审核模式：settings 优先，其次 ``sys_configs``，缺省 platform。"""
    settings = get_settings()
    if settings.marketplace_review_mode:
        return normalize_review_mode(settings.marketplace_review_mode)
    if db is not None:
        row = await db.scalar(select(SystemConfig.value).where(SystemConfig.key == CONFIG_KEY_MODE))
        parsed = _config_scalar(row)
        if parsed:
            return normalize_review_mode(parsed)
    return "platform"


async def get_marketplace_review_tenant_id(db: AsyncSession | None = None) -> UUID | None:
    """读取指定审核租户 ID；配置缺失或非法 UUID 时返回 None。"""
    settings = get_settings()
    if settings.marketplace_review_tenant_id:
        try:
            return UUID(settings.marketplace_review_tenant_id)
        except ValueError:
            return None
    if db is not None:
        row = await db.scalar(select(SystemConfig.value).where(SystemConfig.key == CONFIG_KEY_TENANT))
        parsed = _config_scalar(row)
        if parsed:
            try:
                return UUID(parsed)
            except ValueError:
                return None
    return None


def is_publisher_review_scope() -> bool:
    """是否 publisher 审核范围（仅发布方租户可审）。"""
    return get_settings().marketplace_review_scope.strip().lower() == "publisher"


async def require_tenant_review_allowed(db: AsyncSession, ctx: TenantContext) -> None:
    """校验租户可执行审核；platform/off 或非指定租户时抛 ``ForbiddenError``。"""
    mode = await get_marketplace_review_mode(db)
    if mode == "platform":
        raise ForbiddenError("应用上架由平台运营审核")
    if mode == "off":
        raise ForbiddenError("当前未启用应用审核")
    if not is_publisher_review_scope():
        review_tenant_id = await get_marketplace_review_tenant_id(db)
        if review_tenant_id and ctx.tenant_id != review_tenant_id:
            raise ForbiddenError("无权审核应用市场上架")


async def assert_tenant_can_review_app(db: AsyncSession, ctx: TenantContext, *, publisher_tenant_id: UUID | None) -> None:
    """在租户审核权限之上再校验应用归属（publisher 范围仅限本租户）。"""
    await require_tenant_review_allowed(db, ctx)
    if is_publisher_review_scope():
        if publisher_tenant_id != ctx.tenant_id:
            raise ForbiddenError("仅可审核本租户发布的应用")


async def require_platform_review_allowed(db: AsyncSession) -> None:
    """校验平台可审核；mode 非 platform 时抛 ``ForbiddenError``。"""
    mode = await get_marketplace_review_mode(db)
    if mode != "platform":
        raise ForbiddenError("当前部署模式由租户侧审核")
