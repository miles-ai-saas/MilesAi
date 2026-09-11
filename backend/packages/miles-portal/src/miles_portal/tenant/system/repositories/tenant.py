"""租户主表仓储。"""

from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.repository import BaseRepository
from miles_core.models.platform.tenant import Tenant


class TenantRepository(BaseRepository[Tenant]):
    """租户主表；name 唯一性校验。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Tenant)

    async def ensure_name_unique(self, name: str, *, exclude_id=None) -> None:
        """校验租户名称全局唯一，冲突抛 BadRequestError；更新时用 exclude_id 排除自身。"""
        await self.ensure_unique(Tenant.name, name, message="租户名称已存在", exclude_id=exclude_id)
