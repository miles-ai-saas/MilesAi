"""运营端风控仓储：风险事件、IP 黑名单与限流规则。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import IpBlacklist, RateLimitRule, RiskEvent
from app.core.repository import BaseRepository


class RiskEventRepository(BaseRepository[RiskEvent]):
    """风险事件仓储。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, RiskEvent)


class IpBlacklistRepository(BaseRepository[IpBlacklist]):
    """IP 黑名单仓储。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, IpBlacklist)


class RateLimitRuleRepository(BaseRepository[RateLimitRule]):
    """限流规则仓储。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, RateLimitRule)
