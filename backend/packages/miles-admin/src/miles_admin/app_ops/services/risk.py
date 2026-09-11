"""运营端风控：风险事件、IP 黑名单与限流规则。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_admin.app_ops.repositories.risk import (
    IpBlacklistRepository,
    RateLimitRuleRepository,
    RiskEventRepository,
)
from miles_core.risk.enforce import platform_risk_enforcer
from miles_admin.models import IpBlacklist, RateLimitRule, RiskEvent, RiskSeverity
from miles_admin.app_ops.schemas.risk import (
    IpBlacklistCreate,
    IpBlacklistOut,
    RateLimitRuleCreate,
    RateLimitRuleOut,
    RateLimitRuleUpdate,
    RiskEventOut,
)
from miles_common.schema import PageParams, PageResult


class AdminRiskService:
    """风控事件查询与黑名单/限流规则维护。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.risk_events = RiskEventRepository(db)
        self.ip_blacklist = IpBlacklistRepository(db)
        self.rate_limits = RateLimitRuleRepository(db)

    async def list_risk_events(
        self,
        params: PageParams,
        *,
        severity: RiskSeverity | None = None,
        resolved: bool | None = None,
    ) -> PageResult[RiskEventOut]:
        """分页查询风险事件，可按 severity / resolved 筛选。"""
        filters = []
        if severity:
            filters.append(RiskEvent.severity == severity)
        if resolved is not None:
            filters.append(RiskEvent.is_resolved == resolved)
        page = await self.risk_events.list_page(
            page=params.page,
            size=params.size,
            filters=filters,
            order_by=RiskEvent.created_at.desc(),
        )
        return PageResult(
            items=[RiskEventOut.model_validate(r) for r in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def resolve_risk(self, event_id: UUID) -> RiskEventOut:
        """标记风险事件为已处理。"""
        event = await self.risk_events.get_by_id_or_raise(event_id, label="风险事件不存在")
        event.is_resolved = True
        await self.db.flush()
        return RiskEventOut.model_validate(event)

    async def list_ip_blacklist(self, params: PageParams) -> PageResult[IpBlacklistOut]:
        """分页列出 IP 黑名单。"""
        page = await self.ip_blacklist.list_page(
            page=params.page,
            size=params.size,
            order_by=IpBlacklist.created_at.desc(),
        )
        return PageResult(
            items=[IpBlacklistOut.model_validate(r) for r in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def add_ip_blacklist(self, body: IpBlacklistCreate, admin_id: UUID) -> IpBlacklistOut:
        """新增 IP 黑名单并刷新 enforcer 缓存。"""
        row = await self.ip_blacklist.create(
            ip_address=body.ip_address.strip(),
            reason=body.reason,
            created_by=admin_id,
        )
        platform_risk_enforcer.invalidate_cache()
        return IpBlacklistOut.model_validate(row)

    async def toggle_ip(self, ip_id: UUID, is_active: bool) -> IpBlacklistOut:
        """启用/禁用黑名单条目。"""
        row = await self.ip_blacklist.get_by_id_or_raise(ip_id, label="记录不存在")
        row.is_active = is_active
        await self.db.flush()
        platform_risk_enforcer.invalidate_cache()
        return IpBlacklistOut.model_validate(row)

    async def list_rate_limits(self, params: PageParams) -> PageResult[RateLimitRuleOut]:
        """分页列出 API 限流规则。"""
        page = await self.rate_limits.list_page(
            page=params.page,
            size=params.size,
            order_by=RateLimitRule.created_at.desc(),
        )
        return PageResult(
            items=[RateLimitRuleOut.model_validate(r) for r in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def create_rate_limit(self, body: RateLimitRuleCreate) -> RateLimitRuleOut:
        """创建限流规则并刷新 enforcer 缓存。"""
        row = await self.rate_limits.create(**body.model_dump())
        platform_risk_enforcer.invalidate_cache()
        return RateLimitRuleOut.model_validate(row)

    async def update_rate_limit(self, rule_id: UUID, body: RateLimitRuleUpdate) -> RateLimitRuleOut:
        """更新限流规则并刷新 enforcer 缓存。"""
        row = await self.rate_limits.get_by_id_or_raise(rule_id, label="规则不存在")
        data = body.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        await self.db.flush()
        platform_risk_enforcer.invalidate_cache()
        return RateLimitRuleOut.model_validate(row)
