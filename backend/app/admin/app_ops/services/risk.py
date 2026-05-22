"""运营端风控：风险事件、IP 黑名单与限流规则。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_ops.repositories.risk import (
    IpBlacklistRepository,
    RateLimitRuleRepository,
    RiskEventRepository,
)
from app.admin.models import RiskEvent, RiskSeverity
from app.admin.app_ops.schemas.risk import (
    IpBlacklistCreate,
    IpBlacklistOut,
    RateLimitRuleCreate,
    RateLimitRuleOut,
    RiskEventOut,
)
from app.common.schema import PageParams, PageResult


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
        event = await self.risk_events.get_by_id_or_raise(event_id, label="风险事件不存在")
        event.is_resolved = True
        await self.db.flush()
        return RiskEventOut.model_validate(event)

    async def list_ip_blacklist(self) -> list[IpBlacklistOut]:
        rows = await self.ip_blacklist.list_ordered()
        return [IpBlacklistOut.model_validate(r) for r in rows]

    async def add_ip_blacklist(
        self, body: IpBlacklistCreate, admin_id: UUID
    ) -> IpBlacklistOut:
        row = await self.ip_blacklist.create(
            ip_address=body.ip_address.strip(),
            reason=body.reason,
            created_by=admin_id,
        )
        return IpBlacklistOut.model_validate(row)

    async def toggle_ip(self, ip_id: UUID, is_active: bool) -> IpBlacklistOut:
        row = await self.ip_blacklist.get_by_id_or_raise(ip_id, label="记录不存在")
        row.is_active = is_active
        await self.db.flush()
        return IpBlacklistOut.model_validate(row)

    async def list_rate_limits(self) -> list[RateLimitRuleOut]:
        rows = await self.rate_limits.list_all()
        return [RateLimitRuleOut.model_validate(r) for r in rows]

    async def create_rate_limit(self, body: RateLimitRuleCreate) -> RateLimitRuleOut:
        row = await self.rate_limits.create(**body.model_dump())
        return RateLimitRuleOut.model_validate(row)

    async def update_rate_limit(
        self, rule_id: UUID, *, is_active: bool | None = None, limit_per_minute: int | None = None
    ) -> RateLimitRuleOut:
        row = await self.rate_limits.get_by_id_or_raise(rule_id, label="规则不存在")
        if is_active is not None:
            row.is_active = is_active
        if limit_per_minute is not None:
            row.limit_per_minute = limit_per_minute
        await self.db.flush()
        return RateLimitRuleOut.model_validate(row)
