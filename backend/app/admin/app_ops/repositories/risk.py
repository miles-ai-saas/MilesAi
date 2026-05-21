from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import IpBlacklist, RateLimitRule, RiskEvent
from app.core.repository import BaseRepository


class RiskEventRepository(BaseRepository[RiskEvent]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, RiskEvent)


class IpBlacklistRepository(BaseRepository[IpBlacklist]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, IpBlacklist)

    async def list_ordered(self) -> list[IpBlacklist]:
        result = await self.db.execute(
            select(IpBlacklist).order_by(IpBlacklist.created_at.desc())
        )
        return list(result.scalars().all())


class RateLimitRuleRepository(BaseRepository[RateLimitRule]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, RateLimitRule)

    async def list_all(self) -> list[RateLimitRule]:
        return list((await self.db.execute(select(RateLimitRule))).scalars().all())
