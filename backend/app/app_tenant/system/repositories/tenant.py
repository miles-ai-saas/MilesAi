from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.models.tenant import Tenant


class TenantRepository(BaseRepository[Tenant]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Tenant)

    async def ensure_name_unique(self, name: str, *, exclude_id=None) -> None:
        await self.ensure_unique(Tenant.name, name, message="租户名称已存在", exclude_id=exclude_id)
