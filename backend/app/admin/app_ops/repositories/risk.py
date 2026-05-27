from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import IpBlacklist, RateLimitRule, RiskEvent
from app.core.repository import BaseRepository


class RiskEventRepository(BaseRepository[RiskEvent]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, RiskEvent)


class IpBlacklistRepository(BaseRepository[IpBlacklist]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, IpBlacklist)


class RateLimitRuleRepository(BaseRepository[RateLimitRule]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, RateLimitRule)
